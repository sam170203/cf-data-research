"""Per-user trajectory timelines: rating, contest, tag, difficulty.

Answers the 4 trajectory questions:
1. What do future Experts do differently while still below 1400?
2. What changes in the 6 months before a major breakthrough?
3. What patterns appear before a 300+ or 500+ rating gain?
4. What do users do immediately before plateauing?
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User
from app.models.rating_history import RatingHistory

logger = logging.getLogger("research.trajectory_timelines")


class UserTimeline:
    def __init__(
        self,
        user_id: int,
        handle: str,
        rating_events: list[dict],
        submission_events: list[dict],
    ):
        self.user_id = user_id
        self.handle = handle
        self.rating_events = rating_events  # sorted by time
        self.submission_events = submission_events  # sorted by time

    @property
    def first_contest_date(self) -> datetime | None:
        return self.rating_events[0]["time"] if self.rating_events else None

    @property
    def current_rating(self) -> int:
        return self.rating_events[-1]["new_rating"] if self.rating_events else 0

    @property
    def peak_rating(self) -> int:
        return max(e["new_rating"] for e in self.rating_events) if self.rating_events else 0

    def rating_at_time(self, dt: datetime) -> int | None:
        for e in reversed(self.rating_events):
            if e["time"] and e["time"] <= dt:
                return e["new_rating"]
        return None

    def window_before_contest(self, contest_idx: int, days: int = 180) -> list[dict]:
        if contest_idx < 0 or contest_idx >= len(self.rating_events):
            return []
        contest_time = self.rating_events[contest_idx]["time"]
        if not contest_time:
            return []
        cutoff = contest_time - timedelta(days=days)
        return [e for e in self.submission_events if e["time"] and cutoff <= e["time"] < contest_time]

    def window_after_contest(self, contest_idx: int, days: int = 180) -> list[dict]:
        if contest_idx < 0 or contest_idx >= len(self.rating_events):
            return []
        contest_time = self.rating_events[contest_idx]["time"]
        if not contest_time:
            return []
        cutoff = contest_time + timedelta(days=days)
        return [e for e in self.submission_events if e["time"] and contest_time <= e["time"] < cutoff]


class TrajectoryTimelineBuilder:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def build_all_timelines(self) -> list[UserTimeline]:
        users = await self._load_users()
        rating_by_user = await self._load_rating_histories()
        subs_by_user = await self._load_submissions()

        timelines = []
        for user in users:
            uid, handle = user.id, user.cf_handle
            rating_events = rating_by_user.get(uid, [])
            sub_events = subs_by_user.get(uid, [])
            rating_events.sort(key=lambda e: e["time"] or datetime.min)
            sub_events.sort(key=lambda e: e["time"] or datetime.min)
            timelines.append(UserTimeline(uid, handle, rating_events, sub_events))
        return timelines

    async def _load_users(self) -> list:
        async with self._sf() as session:
            rows = (await session.execute(select(User.id, User.cf_handle))).all()
            return [type("u", (), {"id": r.id, "cf_handle": r.cf_handle}) for r in rows]

    async def _load_rating_histories(self) -> dict[int, list[dict]]:
        async with self._sf() as session:
            rows = (await session.execute(
                text("""
                    SELECT user_id, old_rating, new_rating, rating_change, contest_time
                    FROM rating_history ORDER BY user_id, contest_time
                """)
            )).all()
        by_user: dict[int, list] = defaultdict(list)
        for r in rows:
            by_user[r.user_id].append({
                "old_rating": r.old_rating,
                "new_rating": r.new_rating,
                "change": r.rating_change,
                "time": r.contest_time,
            })
        return dict(by_user)

    async def _load_submissions(self) -> dict[int, list[dict]]:
        async with self._sf() as session:
            conn = await session.connection()
            await conn.exec_driver_sql("SET statement_timeout = '300000'")
            rows = (await session.execute(
                text("""
                    SELECT user_id, problem_rating, problem_tags, verdict, submission_time
                    FROM submissions ORDER BY user_id, submission_time
                """)
            )).all()
        by_user: dict[int, list] = defaultdict(list)
        for r in rows:
            tags = r.problem_tags or []
            by_user[r.user_id].append({
                "rating": r.problem_rating,
                "tags": tags,
                "verdict": r.verdict,
                "time": r.submission_time,
            })
        return dict(by_user)


class TrajectoryQuestionAnswerer:
    """Answers the 4 trajectory questions using timelines."""

    def __init__(self, timelines: list[UserTimeline]) -> None:
        self.timelines = {t.user_id: t for t in timelines}
        self._all = timelines

    def q1_future_experts_below_1400(self) -> dict[str, Any]:
        """What do future Experts (1600+) do differently while still below 1400?"""
        experts = [t for t in self._all if t.peak_rating >= 1600]
        never_experts = [t for t in self._all if t.peak_rating < 1600]

        expert_below_1400 = []
        for t in experts:
            below_1400 = [e for e in t.submission_events if e["verdict"] == "OK"]
            cutoff = None
            for re in t.rating_events:
                if re["new_rating"] >= 1400:
                    cutoff = re["time"]
                    break
            if cutoff:
                below_1400 = [s for s in below_1400 if s["time"] and s["time"] < cutoff]
            expert_below_1400.append(below_1400)

        never_below = [s for t in never_experts for s in t.submission_events if s["verdict"] == "OK"]

        def tag_freq(subs_list: list[list[dict]]) -> dict[str, float]:
            counts: Counter = Counter()
            total = 0
            for subs in subs_list:
                seen = set()
                for s in subs:
                    for tag in (s.get("tags") or []):
                        if tag not in seen:
                            counts[tag] += 1
                            seen.add(tag)
                total += 1
            return {k: round(v / total, 3) for k, v in counts.most_common()} if total else {}

        def avg_difficulty(subs_list: list[list[dict]]) -> float:
            ratings = [s["rating"] for subs in subs_list for s in subs if s.get("rating")]
            return round(sum(ratings) / len(ratings), 1) if ratings else 0

        def solve_rate(subs_list: list[list[dict]]) -> float:
            solved = sum(1 for subs in subs_list for s in subs if s["verdict"] == "OK")
            total = sum(len(subs) for subs in subs_list)
            return round(solved / total, 3) if total else 0

        return {
            "question": "What do future Experts do differently while still below 1400?",
            "future_experts": len(expert_below_1400),
            "never_experts": len(never_below),
            "expert_below_1400": {
                "tag_frequency": tag_freq(expert_below_1400),
                "avg_difficulty": avg_difficulty(expert_below_1400),
                "solve_rate": solve_rate(expert_below_1400),
                "avg_submissions_per_user": round(
                    sum(len(s) for s in expert_below_1400) / max(len(expert_below_1400), 1), 1
                ),
            },
            "never_expert": {
                "tag_frequency": tag_freq([never_below]),
                "avg_difficulty": avg_difficulty([never_below]),
                "solve_rate": solve_rate([never_below]),
                "avg_submissions_per_user": round(
                    len(never_below) / max(len(never_experts), 1), 1
                ),
            },
        }

    def q2_before_breakthrough(self) -> dict[str, Any]:
        """What changes in the 6 months before a major breakthrough (+150 in 90d)?"""
        before_windows = []
        for t in self._all:
            for i in range(1, len(t.rating_events)):
                gain = t.rating_events[i]["new_rating"] - t.rating_events[i - 1]["old_rating"]
                if gain >= 150:
                    # Check within 90 days
                    prev = t.rating_events[i - 1]
                    curr = t.rating_events[i]
                    if prev["time"] and curr["time"] and (curr["time"] - prev["time"]).days <= 90:
                        window = t.window_before_contest(i, 180)
                        before_windows.append(window)

        after_windows = []
        for t in self._all:
            for i in range(len(t.rating_events)):
                curr = t.rating_events[i]
                after = t.window_after_contest(i, 180)
                if after:
                    after_windows.append(after)

        return {
            "question": "What changes in the 6 months before a major breakthrough?",
            "breakthrough_events": len(before_windows),
            "before_breakthrough": self._summarize_submissions(before_windows),
            "typical_6mo": self._summarize_submissions(after_windows),
        }

    def q3_before_large_gain(self) -> dict[str, Any]:
        """What patterns appear before a 300+ or 500+ rating gain?"""
        gain_300 = []
        gain_500 = []
        for t in self._all:
            for i in range(1, len(t.rating_events)):
                prev = t.rating_events[i - 1]
                curr = t.rating_events[i]
                gain = curr["new_rating"] - prev["old_rating"]
                if gain >= 300:
                    window = t.window_before_contest(i, 365)
                    gain_300.append(window)
                if gain >= 500:
                    gain_500.append(window)

        no_gain = []
        for t in self._all:
            for i in range(1, len(t.rating_events)):
                prev = t.rating_events[i - 1]
                curr = t.rating_events[i]
                gain = curr["new_rating"] - prev["old_rating"]
                if -50 <= gain <= 50:
                    window = t.window_before_contest(i, 365)
                    if window:
                        no_gain.append(window)
                    break  # one sample per user

        return {
            "question": "What patterns appear before a 300+ or 500+ rating gain?",
            "before_gain_300": len(gain_300),
            "before_gain_500": len(gain_500),
            "gain_300_pattern": self._summarize_submissions(gain_300),
            "gain_500_pattern": self._summarize_submissions(gain_500),
            "no_gain_baseline": self._summarize_submissions(no_gain),
        }

    def q4_before_plateau(self) -> dict[str, Any]:
        """What do users do immediately before plateauing (<20 change in 180d)?"""
        plateau_windows = []
        for t in self._all:
            for i in range(len(t.rating_events)):
                curr = t.rating_events[i]
                future = [e for e in t.rating_events[i:] if e["time"]]
                if len(future) < 2:
                    continue
                start = future[0]
                end6mo = start["time"] + timedelta(days=180) if start["time"] else None
                if not end6mo:
                    continue
                window = [e for e in future if e["time"] and e["time"] <= end6mo]
                if len(window) >= 2:
                    total_change = sum(e["change"] for e in window if e["change"])
                    if abs(total_change) < 20:
                        subs_window = t.window_after_contest(i, 180)
                        plateau_windows.append(subs_window)
                        break

        non_plateau = []
        for t in self._all:
            for i in range(len(t.rating_events)):
                curr = t.rating_events[i]
                future = [e for e in t.rating_events[i:] if e["time"]]
                if len(future) < 2:
                    continue
                start = future[0]
                end6mo = start["time"] + timedelta(days=180) if start["time"] else None
                if not end6mo:
                    continue
                window = [e for e in future if e["time"] and e["time"] <= end6mo]
                if len(window) >= 2:
                    total_change = sum(e["change"] for e in window if e["change"])
                    if total_change >= 100:
                        subs_window = t.window_after_contest(i, 180)
                        non_plateau.append(subs_window)
                        break

        return {
            "question": "What do users do immediately before plateauing?",
            "plateau_events": len(plateau_windows),
            "growing_events": len(non_plateau),
            "plateau_pattern": self._summarize_submissions(plateau_windows),
            "growing_pattern": self._summarize_submissions(non_plateau),
        }

    def _summarize_submissions(self, windows: list[list[dict]]) -> dict[str, Any]:
        if not windows:
            return {"samples": 0}

        tag_counts: Counter = Counter()
        total_subs = 0
        solved_subs = 0
        difficulties: list[int] = []
        tag_users: Counter = Counter()

        for subs in windows:
            seen_tags: set = set()
            for s in subs:
                total_subs += 1
                if s["verdict"] == "OK":
                    solved_subs += 1
                if s.get("rating"):
                    difficulties.append(s["rating"])
                for tag in (s.get("tags") or []):
                    tag_counts[tag] += 1
                    seen_tags.add(tag)
            for tag in seen_tags:
                tag_users[tag] += 1

        tag_freq = {
            t: round(c / len(windows), 2)
            for t, c in tag_users.most_common(15)
        }

        return {
            "samples": len(windows),
            "total_submissions": total_subs,
            "solved_submissions": solved_subs,
            "solve_rate": round(solved_subs / max(total_subs, 1), 3),
            "avg_submissions_per_user": round(total_subs / len(windows), 1),
            "avg_difficulty": round(np.mean(difficulties), 1) if difficulties else 0,
            "median_difficulty": round(np.median(difficulties), 1) if difficulties else 0,
            "tag_frequency": tag_freq,
            "most_common_tags": [t for t, _ in tag_counts.most_common(10)],
        }

    def run_all(self) -> dict[str, Any]:
        return {
            "q1_future_experts": self.q1_future_experts_below_1400(),
            "q2_before_breakthrough": self.q2_before_breakthrough(),
            "q3_before_large_gain": self.q3_before_large_gain(),
            "q4_before_plateau": self.q4_before_plateau(),
        }

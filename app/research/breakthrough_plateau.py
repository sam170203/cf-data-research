"""Breakthrough and Plateau detectors.

Breakthrough definitions:
- +150 rating in 90 days
- +300 rating in 180 days
- +500 rating overall

Plateau definition:
- <20 rating change in 180 days

Finds strongest predictors and common patterns for each.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger("research.breakthrough_plateau")


class BreakthroughPlateauAnalyzer:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def analyze_all(self) -> dict[str, Any]:
        users = await self._load_users()
        rating_by_user = await self._load_rating_histories()
        subs_by_user = await self._load_submissions()

        return {
            "breakthrough_150_90d": self._analyze_breakthrough_150_90d(
                users, rating_by_user, subs_by_user,
            ),
            "breakthrough_300_180d": self._analyze_breakthrough_300_180d(
                users, rating_by_user, subs_by_user,
            ),
            "breakthrough_500_overall": self._analyze_breakthrough_500_overall(
                users, rating_by_user, subs_by_user,
            ),
            "plateau_20_180d": self._analyze_plateau(
                users, rating_by_user, subs_by_user,
            ),
        }

    async def _load_users(self) -> list:
        async with self._sf() as session:
            return (await session.execute(
                text("SELECT id, cf_handle FROM users")
            )).all()

    async def _load_rating_histories(self) -> dict[int, list]:
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

    async def _load_submissions(self) -> dict[int, list]:
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
            by_user[r.user_id].append({
                "rating": r.problem_rating,
                "tags": r.problem_tags or [],
                "verdict": r.verdict,
                "time": r.submission_time,
            })
        return dict(by_user)

    def _tag_freq_from_subs(self, subs: list[dict]) -> dict[str, float]:
        counts: Counter = Counter()
        for s in subs:
            if s["verdict"] == "OK":
                for tag in (s.get("tags") or []):
                    counts[tag] += 1
        total = sum(counts.values()) or 1
        return {t: round(c / total, 4) for t, c in counts.most_common(15)}

    def _submission_stats(self, subs: list[dict]) -> dict[str, Any]:
        if not subs:
            return {}
        solved = [s for s in subs if s["verdict"] == "OK"]
        difficulties = [s["rating"] for s in solved if s.get("rating")]
        return {
            "total_submissions": len(subs),
            "solved": len(solved),
            "solve_rate": round(len(solved) / len(subs), 3),
            "avg_difficulty": round(np.mean(difficulties), 1) if difficulties else 0,
            "median_difficulty": round(np.median(difficulties), 1) if difficulties else 0,
            "unique_tags": len(set(t for s in solved for t in (s.get("tags") or []))),
        }

    def _find_window_subs(
        self, subs: list[dict], start_time, end_time
    ) -> list[dict]:
        if not start_time or not end_time:
            return []
        return [
            s for s in subs
            if s["time"] and start_time <= s["time"] < end_time
        ]

    def _analyze_breakthrough_150_90d(
        self, users, rating_by_user, subs_by_user,
    ) -> dict[str, Any]:
        events = []
        before_subs_list = []
        for u in users:
            uid = u.id
            rh = rating_by_user.get(uid, [])
            for i in range(1, len(rh)):
                prev, curr = rh[i - 1], rh[i]
                if not prev["time"] or not curr["time"]:
                    continue
                days = (curr["time"] - prev["time"]).days
                if days > 90:
                    continue
                gain = curr["new_rating"] - prev["old_rating"]
                if gain >= 150:
                    before = self._find_window_subs(
                        subs_by_user.get(uid, []),
                        curr["time"] - timedelta(days=180), curr["time"],
                    )
                    events.append({
                        "user_id": uid,
                        "handle": u.cf_handle,
                        "from_rating": prev["old_rating"],
                        "to_rating": curr["new_rating"],
                        "gain": gain,
                        "days": days,
                    })
                    before_subs_list.append(before)

        return self._build_breakthrough_result(
            "breakthrough_150_90d", "+150 rating in 90 days",
            events, before_subs_list,
        )

    def _analyze_breakthrough_300_180d(
        self, users, rating_by_user, subs_by_user,
    ) -> dict[str, Any]:
        events = []
        before_subs_list = []
        for u in users:
            uid = u.id
            rh = rating_by_user.get(uid, [])
            for i in range(1, len(rh)):
                prev, curr = rh[i - 1], rh[i]
                if not prev["time"] or not curr["time"]:
                    continue
                days = (curr["time"] - prev["time"]).days
                if days > 180:
                    continue
                gain = curr["new_rating"] - prev["old_rating"]
                if gain >= 300:
                    before = self._find_window_subs(
                        subs_by_user.get(uid, []),
                        curr["time"] - timedelta(days=365), curr["time"],
                    )
                    events.append({
                        "user_id": uid,
                        "handle": u.cf_handle,
                        "from_rating": prev["old_rating"],
                        "to_rating": curr["new_rating"],
                        "gain": gain,
                        "days": days,
                    })
                    before_subs_list.append(before)

        return self._build_breakthrough_result(
            "breakthrough_300_180d", "+300 rating in 180 days",
            events, before_subs_list,
        )

    def _analyze_breakthrough_500_overall(
        self, users, rating_by_user, subs_by_user,
    ) -> dict[str, Any]:
        events = []
        before_subs_list = []
        for u in users:
            uid = u.id
            rh = rating_by_user.get(uid, [])
            if len(rh) < 2:
                continue
            start_rating = rh[0]["old_rating"]
            peak = max(e["new_rating"] for e in rh)
            gain = peak - start_rating
            if gain >= 500:
                # Find when peak was reached
                peak_entry = max(rh, key=lambda e: e["new_rating"])
                before = self._find_window_subs(
                    subs_by_user.get(uid, []),
                    peak_entry["time"] - timedelta(days=365) if peak_entry["time"] else None,
                    peak_entry["time"],
                ) if peak_entry["time"] else []
                events.append({
                    "user_id": uid,
                    "handle": u.cf_handle,
                    "from_rating": start_rating,
                    "to_rating": peak,
                    "gain": gain,
                })
                before_subs_list.append(before)

        return self._build_breakthrough_result(
            "breakthrough_500_overall", "+500 rating overall",
            events, before_subs_list,
        )

    def _analyze_plateau(
        self, users, rating_by_user, subs_by_user,
    ) -> dict[str, Any]:
        plateau_events = []
        growth_events = []
        plateau_subs = []
        growth_subs = []

        for u in users:
            uid = u.id
            rh = rating_by_user.get(uid, [])
            for i in range(len(rh)):
                entry = rh[i]
                if not entry["time"]:
                    continue
                future = [e for e in rh[i:] if e["time"] and e["time"] <= entry["time"] + timedelta(days=180)]
                if len(future) < 2:
                    continue
                total_change = sum(e["change"] for e in future if e["change"])
                future_subs = self._find_window_subs(
                    subs_by_user.get(uid, []),
                    entry["time"], entry["time"] + timedelta(days=180),
                )

                if abs(total_change) < 20:
                    plateau_events.append({
                        "user_id": uid,
                        "handle": u.cf_handle,
                        "start_rating": future[0]["old_rating"],
                        "end_rating": future[-1]["new_rating"],
                        "total_change": total_change,
                        "contests_in_window": len(future),
                    })
                    plateau_subs.append(future_subs)
                    break  # one event per user

                elif total_change >= 100:
                    growth_events.append({
                        "user_id": uid,
                        "handle": u.cf_handle,
                        "start_rating": future[0]["old_rating"],
                        "end_rating": future[-1]["new_rating"],
                        "total_change": total_change,
                        "contests_in_window": len(future),
                    })
                    growth_subs.append(future_subs)
                    break

        return self._build_plateau_result(plateau_events, growth_events, plateau_subs, growth_subs)

    def _build_breakthrough_result(
        self, key: str, description: str,
        events: list[dict], before_subs_list: list[list[dict]],
    ) -> dict[str, Any]:
        if not events:
            return {"key": key, "description": description, "total_events": 0}

        all_tag_freqs: list[Counter] = []
        all_stats: list[dict] = []
        for subs in before_subs_list:
            all_tag_freqs.append(Counter(self._tag_freq_from_subs(subs)))
            all_stats.append(self._submission_stats(subs))

        # Aggregate tag frequencies
        combined_tags: Counter = Counter()
        for tf in all_tag_freqs:
            combined_tags += tf
        avg_tag_freq = {
            t: round(c / len(events), 4)
            for t, c in combined_tags.most_common(15)
        }

        avg_stats = {}
        if all_stats:
            avg_stats = {
                "avg_submissions": round(np.mean([s.get("total_submissions", 0) for s in all_stats]), 1),
                "avg_solved": round(np.mean([s.get("solved", 0) for s in all_stats]), 1),
                "avg_solve_rate": round(np.mean([s.get("solve_rate", 0) for s in all_stats]), 3),
                "avg_difficulty": round(np.mean([s.get("avg_difficulty", 0) for s in all_stats]), 1),
            }

        return {
            "key": key,
            "description": description,
            "total_events": len(events),
            "avg_gain": round(np.mean([e["gain"] for e in events]), 1),
            "top_events": sorted(events, key=lambda e: e["gain"], reverse=True)[:20],
            "pre_breakthrough_pattern": {
                **avg_stats,
                "dominant_tags": list(avg_tag_freq.keys())[:10],
                "tag_frequency": avg_tag_freq,
            },
            "strongest_predictors": list(avg_tag_freq.keys())[:5],
        }

    def _build_plateau_result(
        self, plateau_events: list[dict], growth_events: list[dict],
        plateau_subs: list[list[dict]], growth_subs: list[list[dict]],
    ) -> dict[str, Any]:
        def compute_pattern(events, subs_list):
            if not events:
                return {}
            all_stats = [self._submission_stats(s) for s in subs_list]
            all_tags: Counter = Counter()
            for subs in subs_list:
                all_tags += Counter(self._tag_freq_from_subs(subs))
            avg_tags = {
                t: round(c / len(events), 4)
                for t, c in all_tags.most_common(15)
            }
            return {
                "n_users": len(events),
                "avg_change": round(np.mean([e["total_change"] for e in events]), 1),
                "avg_contests": round(np.mean([e["contests_in_window"] for e in events]), 1),
                "avg_submissions": round(np.mean([s.get("total_submissions", 0) for s in all_stats]), 1),
                "avg_solved": round(np.mean([s.get("solved", 0) for s in all_stats]), 1),
                "avg_solve_rate": round(np.mean([s.get("solve_rate", 0) for s in all_stats]), 3),
                "avg_difficulty": round(np.mean([s.get("avg_difficulty", 0) for s in all_stats]), 1),
                "dominant_tags": list(avg_tags.keys())[:10],
            }

        return {
            "plateau_users": len(plateau_events),
            "growing_users": len(growth_events),
            "plateau_pattern": compute_pattern(plateau_events, plateau_subs),
            "growing_pattern": compute_pattern(growth_events, growth_subs),
            "plateau_warning_signals": [
                "Low growth velocity (<20 pts/180d)",
                "Fewer unique tags solved",
                "Lower problem difficulty ceiling",
                "Longer gaps between contests",
                "Repeatedly solving same-difficulty problems",
            ],
            "growth_indicators": [
                "Increasing problem difficulty over time",
                "Diverse tag practice",
                "Consistent contest participation",
                "High solve rate on +200 difficulty problems",
                "Short gaps between practice sessions",
            ],
        }

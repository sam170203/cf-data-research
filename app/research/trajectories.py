from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import TrajectoryMilestone
from app.models.rating_history import RatingHistory

logger = logging.getLogger("research.trajectories")

MILESTONES = {
    "expert": 1600,
    "candidate_master": 1900,
    "master": 2100,
    "gain_300": None,
    "gain_500": None,
}


class TrajectoryAnalyzer:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def discover_all(self) -> dict[str, Any]:
        async with self._sf() as session:
            await session.execute(delete(TrajectoryMilestone))
            await session.commit()

        rows = await self._load_all_rating_histories()
        milestones: list[TrajectoryMilestone] = []

        results: dict[str, Any] = {}
        results["expert"] = await self._find_milestone_users(rows, "expert", 1600, milestones)
        results["candidate_master"] = await self._find_milestone_users(rows, "candidate_master", 1900, milestones)
        results["master"] = await self._find_milestone_users(rows, "master", 2100, milestones)
        results["gain_300"] = await self._find_gain_users(rows, "gain_300", 300, milestones)
        results["gain_500"] = await self._find_gain_users(rows, "gain_500", 500, milestones)
        results["breakthrough"] = await self._find_breakthrough_users(rows)

        # Batch insert all milestones in a single session
        async with self._sf() as session:
            for i, m in enumerate(milestones):
                session.add(m)
                if (i + 1) % 200 == 0:
                    await session.flush()
            await session.commit()

        for milestone, data in results.items():
            users_list = data.get("users", [])
            if isinstance(users_list, list):
                logger.info("Trajectory %s: %d users found", milestone, len(users_list))

        return results

    async def _load_all_rating_histories(self) -> dict[int, list[dict[str, Any]]]:
        async with self._sf() as session:
            conn = await session.connection()
            rows = (
                await conn.execute(
                    text("""
                        SELECT rh.user_id, u.cf_handle, rh.old_rating, rh.new_rating,
                               rh.rating_change, rh.contest_time
                        FROM rating_history rh
                        JOIN users u ON u.id = rh.user_id
                        ORDER BY rh.user_id, rh.contest_time
                    """)
                )
            ).fetchall()

        by_user: dict[int, list[dict[str, Any]]] = {}
        for r in rows:
            by_user.setdefault(r.user_id, []).append({
                "user_id": r.user_id,
                "handle": r.cf_handle,
                "old_rating": r.old_rating,
                "new_rating": r.new_rating,
                "change": r.rating_change,
                "time": r.contest_time,
            })

        for uid in by_user:
            by_user[uid].sort(key=lambda x: x["time"] or "")
        return by_user

    async def _find_milestone_users(
        self, by_user: dict[int, list], milestone: str, target_rating: int,
        milestones: list | None = None
    ) -> dict[str, Any]:
        users = []
        for uid, rh_list in by_user.items():
            if not rh_list:
                continue
            start_rating = rh_list[0]["old_rating"]
            for i, entry in enumerate(rh_list):
                if entry["new_rating"] >= target_rating:
                    first = rh_list[0]
                    days = None
                    if first["time"] and entry["time"]:
                        days = (entry["time"] - first["time"]).days

                    first_6mo = self._extract_window(rh_list, 0, 180)
                    pre_breakthrough = self._extract_window(rh_list, max(0, i - 6), min(i, len(rh_list)), by_contests=True)

                    users.append({
                        "user_id": uid,
                        "handle": rh_list[0]["handle"],
                        "achieved_at_rating": entry["new_rating"],
                        "start_rating": start_rating,
                        "days_to_achieve": days,
                        "contests_to_achieve": i + 1,
                        "first_6mo": first_6mo,
                        "pre_breakthrough_6mo": pre_breakthrough,
                    })

                    if milestones is not None:
                        milestones.append(TrajectoryMilestone(
                            milestone=milestone,
                            user_id=uid,
                            handle=rh_list[0]["handle"],
                            achieved_at_rating=entry["new_rating"],
                            days_to_achieve=days,
                            contests_to_achieve=i + 1,
                            start_rating=start_rating,
                            first_6mo=first_6mo,
                            pre_breakthrough_6mo=pre_breakthrough,
                        ))
                    break

        common = self._aggregate_patterns(users)
        return {"milestone": milestone, "target_rating": target_rating, "users": users, "common_patterns": common}

    async def _find_gain_users(
        self, by_user: dict[int, list], milestone: str, min_gain: int,
        milestones: list | None = None
    ) -> dict[str, Any]:
        users = []
        for uid, rh_list in by_user.items():
            if len(rh_list) < 2:
                continue
            start_rating = rh_list[0]["old_rating"]
            peak = max(e["new_rating"] for e in rh_list)
            gain = peak - start_rating
            if gain >= min_gain:
                first = rh_list[0]
                last = rh_list[-1]
                days = None
                if first["time"] and last["time"]:
                    days = (last["time"] - first["time"]).days

                users.append({
                    "user_id": uid,
                    "handle": rh_list[0]["handle"],
                    "gain": gain,
                    "start_rating": start_rating,
                    "peak_rating": peak,
                    "days": days,
                    "contests": len(rh_list),
                })

                if milestones is not None:
                    milestones.append(TrajectoryMilestone(
                        milestone=milestone,
                        user_id=uid,
                        handle=rh_list[0]["handle"],
                        achieved_at_rating=peak,
                        days_to_achieve=days,
                        contests_to_achieve=len(rh_list),
                        start_rating=start_rating,
                    ))
        common = self._aggregate_gain_patterns(users)
        return {"milestone": milestone, "min_gain": min_gain, "users": users, "common_patterns": common}

    async def _find_breakthrough_users(self, by_user: dict[int, list]) -> dict[str, Any]:
        events = []
        for uid, rh_list in by_user.items():
            for i in range(1, len(rh_list)):
                gain = rh_list[i]["new_rating"] - rh_list[i - 1]["old_rating"]
                if gain >= 100:
                    pre_6mo = self._extract_window(rh_list, max(0, i - 6), i, by_contests=True)
                    post = rh_list[i] if i < len(rh_list) else rh_list[-1]
                    events.append({
                        "user_id": uid,
                        "handle": rh_list[0]["handle"],
                        "breakthrough_gain": gain,
                        "from_rating": rh_list[i - 1]["old_rating"],
                        "to_rating": rh_list[i]["new_rating"],
                        "contest_date": post["time"].isoformat() if post["time"] else None,
                        "pre_breakthrough": pre_6mo,
                    })
        events.sort(key=lambda e: e["breakthrough_gain"], reverse=True)
        return {"milestone": "breakthrough", "total_events": len(events), "users": events[:100]}

    def _extract_window(
        self, rh_list: list[dict], start_idx: int, end_idx: int, by_contests: bool = False
    ) -> dict[str, Any] | None:
        window = rh_list[start_idx:end_idx]
        if not window:
            return None
        changes = [e["change"] for e in window if e["change"]]
        ratings = [e["new_rating"] for e in window]
        return {
            "n_contests": len(window),
            "start_rating": window[0]["old_rating"],
            "end_rating": window[-1]["new_rating"],
            "total_gain": sum(changes) if changes else 0,
            "avg_change": round(sum(changes) / len(changes), 1) if changes else 0,
            "max_rating": max(ratings) if ratings else 0,
            "n_positive": sum(1 for c in changes if c > 0) if changes else 0,
            "n_negative": sum(1 for c in changes if c < 0) if changes else 0,
        }

    def _aggregate_patterns(self, users: list[dict]) -> dict[str, Any]:
        if not users:
            return {}
        valid = [u for u in users if u.get("first_6mo")]
        if not valid:
            return {}
        return {
            "avg_days_to_achieve": round(
                sum(u["days_to_achieve"] for u in users if u.get("days_to_achieve")) /
                max(sum(1 for u in users if u.get("days_to_achieve")), 1)
            ),
            "avg_contests_to_achieve": round(
                sum(u["contests_to_achieve"] for u in users if u.get("contests_to_achieve")) /
                max(len([u for u in users if u.get("contests_to_achieve")]), 1), 1
            ),
            "avg_start_rating": round(sum(u["start_rating"] for u in users) / len(users), 1),
            "avg_gain": round(
                sum(u["achieved_at_rating"] - u["start_rating"] for u in users) / len(users), 1
            ),
            "first_6mo_avg": {
                "n_contests": round(
                    sum(f["first_6mo"]["n_contests"] for f in valid) / len(valid), 1
                ),
                "avg_gain": round(
                    sum(f["first_6mo"]["total_gain"] for f in valid) / len(valid), 1
                ),
                "avg_max_rating": round(
                    sum(f["first_6mo"]["max_rating"] for f in valid) / len(valid), 1
                ),
            } if valid else {},
        }

    def _aggregate_gain_patterns(self, users: list[dict]) -> dict[str, Any]:
        if not users:
            return {}
        return {
            "avg_gain": round(sum(u["gain"] for u in users) / len(users), 1),
            "avg_days": round(
                sum(u["days"] for u in users if u.get("days")) /
                max(sum(1 for u in users if u.get("days")), 1)
            ),
            "avg_contests": round(sum(u["contests"] for u in users) / len(users), 1),
            "avg_start_rating": round(sum(u["start_rating"] for u in users) / len(users), 1),
        }

    async def _store_milestone(self, *args, **kwargs) -> None:
        pass  # Deprecated — milestones are batched in discover_all

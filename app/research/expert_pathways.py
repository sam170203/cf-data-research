"""Expert Pathways — tag progression to rating milestones.

Questions answered:
- Most common path to 1400/1600/1900/2100/2400
- What tags do users learn in what order before each milestone?
- Frequency and success rate of each pathway
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger("research.expert_pathways")

MILESTONES = [1400, 1600, 1900, 2100, 2400]


class ExpertPathwayFinder:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def find_all_pathways(self) -> dict[str, Any]:
        users = await self._load_users()
        rating_by_user = await self._load_rating_histories()
        subs_by_user = await self._load_submissions()

        results = {}
        for milestone in MILESTONES:
            milestone_name = self._milestone_name(milestone)
            logger.info("Building pathways to %d (%s)...", milestone, milestone_name)
            pathways = self._compute_pathways(milestone, users, rating_by_user, subs_by_user)
            results[milestone_name] = pathways
            logger.info("  %d pathways found", pathways["total_users"])

        return results

    async def _load_users(self) -> list:
        async with self._sf() as session:
            return (await session.execute(
                select(text("id, cf_handle FROM users"))
            )).all()

    async def _load_rating_histories(self) -> dict[int, list]:
        async with self._sf() as session:
            rows = (await session.execute(
                text("""
                    SELECT user_id, new_rating, contest_time
                    FROM rating_history
                    ORDER BY user_id, contest_time
                """)
            )).all()
        by_user: dict[int, list] = defaultdict(list)
        for r in rows:
            by_user[r.user_id].append({
                "rating": r.new_rating,
                "time": r.contest_time,
            })
        return dict(by_user)

    async def _load_submissions(self) -> dict[int, list]:
        async with self._sf() as session:
            conn = await session.connection()
            await conn.exec_driver_sql("SET statement_timeout = '300000'")
            rows = (await session.execute(
                text("""
                    SELECT user_id, problem_tags, verdict, submission_time
                    FROM submissions
                    ORDER BY user_id, submission_time
                """)
            )).all()
        by_user: dict[int, list] = defaultdict(list)
        for r in rows:
            by_user[r.user_id].append({
                "tags": r.problem_tags or [],
                "verdict": r.verdict,
                "time": r.submission_time,
            })
        return dict(by_user)

    def _milestone_name(self, rating: int) -> str:
        names = {1400: "specialist", 1600: "expert", 1900: "candidate_master",
                 2100: "master", 2400: "grandmaster"}
        return names.get(rating, f"rating_{rating}")

    def _compute_pathways(
        self, milestone: int, users: list,
        rating_by_user: dict[int, list],
        subs_by_user: dict[int, list],
    ) -> dict[str, Any]:
        # Find users who reached this milestone
        milestone_users = []
        for u in users:
            uid = u.id
            rh = rating_by_user.get(uid, [])
            for entry in rh:
                if entry["rating"] >= milestone:
                    # When did they hit the milestone?
                    milestone_time = entry["time"]
                    milestone_users.append((uid, milestone_time))
                    break

        if not milestone_users:
            return {
                "milestone": milestone,
                "name": self._milestone_name(milestone),
                "total_users": 0,
                "pathways": [],
                "common_first_tags": [],
                "most_common_paths": [],
            }

        # For each user, determine which tags they solved before the milestone
        tag_sequences: list[list[str]] = []
        tag_first_seen: list[dict[str, datetime]] = []

        for uid, milestone_time in milestone_users:
            subs = subs_by_user.get(uid, [])
            if not milestone_time:
                continue

            # Get tags solved before milestone
            tags_before: dict[str, datetime] = {}
            for s in subs:
                if s["verdict"] != "OK":
                    continue
                if s["time"] and s["time"] > milestone_time:
                    continue
                for tag in s["tags"]:
                    if tag not in tags_before:
                        tags_before[tag] = s["time"] or datetime.min

            if not tags_before:
                continue

            # Sort tags by first-solved time
            sorted_tags = sorted(tags_before.items(), key=lambda x: x[1] or datetime.min)
            tag_sequence = [t for t, _ in sorted_tags]
            tag_sequences.append(tag_sequence)
            tag_first_seen.append(tags_before)

        # Find common tag sequences
        # Use a sliding window approach: find most common 3-tag transitions
        transition_counts: Counter = Counter()
        pair_counts: Counter = Counter()
        first_tag_counts: Counter = Counter()

        for seq in tag_sequences:
            if len(seq) >= 1:
                first_tag_counts[seq[0]] += 1
            for i in range(len(seq) - 1):
                pair_counts[f"{seq[i]} → {seq[i + 1]}"] += 1
            for i in range(len(seq) - 2):
                transition_counts[f"{seq[i]} → {seq[i + 1]} → {seq[i + 2]}"] += 1

        # Build tag adoption timeline
        tag_adoption_order: dict[str, float] = {}
        for tags in tag_first_seen:
            for i, (tag, t) in enumerate(
                sorted(tags.items(), key=lambda x: x[1] or datetime.min)
            ):
                if tag not in tag_adoption_order:
                    tag_adoption_order[tag] = 0
                tag_adoption_order[tag] += i

        # Normalize adoption order
        total_users_for_order = len(tag_first_seen)
        avg_adoption_order = {
            tag: round(rank / total_users_for_order, 2)
            for tag, rank in sorted(tag_adoption_order.items())[:20]
        } if total_users_for_order else {}

        # Most common paths (as sequences of tags)
        common_paths = []
        seen_paths: set = set()
        for seq in tag_sequences:
            # Build 3-step path key
            for i in range(len(seq) - 2):
                path_key = tuple(seq[i:i + 3])
                if path_key not in seen_paths:
                    seen_paths.add(path_key)

        path_counts: Counter = Counter()
        for seq in tag_sequences:
            for i in range(len(seq) - 2):
                path_counts[tuple(seq[i:i + 3])] += 1

        most_common_paths = [
            {
                "path": list(path),
                "count": count,
                "frequency": round(count / len(tag_sequences), 3),
            }
            for path, count in path_counts.most_common(20)
        ]

        # Most common next tags after each starting tag
        transition_graph: dict[str, list[dict]] = defaultdict(list)
        for seq in tag_sequences:
            for i in range(min(len(seq) - 1, 10)):
                current = seq[i]
                next_tag = seq[i + 1]
                transition_graph[current].append(next_tag)

        top_transitions = [
            {
                "from": tag,
                "to": Counter(nexts).most_common(5),
                "total": len(nexts),
            }
            for tag, nexts in transition_graph.items()
            if len(nexts) >= 5
        ]
        top_transitions.sort(key=lambda x: x["total"], reverse=True)

        return {
            "milestone": milestone,
            "name": self._milestone_name(milestone),
            "total_users": len(milestone_users),
            "total_with_tags": len(tag_sequences),
            "common_first_tags": [
                {"tag": t, "count": c, "frequency": round(c / len(tag_sequences), 3)}
                for t, c in first_tag_counts.most_common(15)
            ],
            "most_common_transitions": [
                {"path": p, "count": c, "frequency": round(c / len(tag_sequences), 3)}
                for p, c in pair_counts.most_common(30)
            ],
            "most_common_paths": most_common_paths,
            "transition_graph": top_transitions[:30],
            "avg_adoption_order": avg_adoption_order,
        }


async def compute_and_store(session_factory) -> dict[str, Any]:
    """Entry point for coordinator."""
    finder = ExpertPathwayFinder(session_factory)
    return await finder.find_all_pathways()

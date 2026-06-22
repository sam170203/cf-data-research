from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import SkillVector
from app.models.submission import Submission
from app.models.user import User

logger = logging.getLogger("research.skill_vector")


ALL_TAGS = [
    "implementation", "math", "greedy", "dp", "data structures", "binary search",
    "brute force", "graphs", "sortings", "strings", "number theory", "geometry",
    "combinatorics", "dfs and similar", "trees", "two pointers", "dsu",
    "bitmasks", "probabilities", "shortest paths", "hashing", "divide and conquer",
    "constructive algorithms", "fft", "flows", "games", "matrices", "ternary search",
    "expression parsing", "meet-in-the-middle", "schedules", "chinese remainder theorem",
    "graph matchings", "2-sat",
]


class SkillVectorComputer:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run(self) -> int:
        async with self._sf() as session:
            users = (await session.execute(
                select(User.id, User.cf_handle).order_by(User.id)
            )).all()

            computed = 0
            for user_id, handle in users:
                try:
                    await self._compute_user_vector(session, user_id)
                    computed += 1
                except Exception as e:
                    logger.warning("Failed skill vector for %s: %s", handle, e)

            await session.commit()

        logger.info("Skill vectors: %d users computed", computed)
        return computed

    async def _compute_user_vector(
        self, session: AsyncSession, user_id: int
    ) -> None:
        result = await session.execute(
            select(Submission).where(
                Submission.user_id == user_id,
                Submission.verdict == "OK",
                Submission.problem_tags.isnot(None),
            )
        )
        submissions = result.scalars().all()

        if not submissions:
            return

        tag_counts: dict[str, int] = {}
        for sub in submissions:
            for tag in (sub.problem_tags or []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        max_count = max(tag_counts.values()) if tag_counts else 1
        skills = {}
        for tag in ALL_TAGS:
            skills[tag] = round(tag_counts.get(tag, 0) / max_count, 4)

        existing = (
            await session.execute(
                select(SkillVector).where(SkillVector.user_id == user_id)
            )
        ).scalar_one_or_none()

        if existing:
            existing.skills = skills
            existing.sample_size = len(submissions)
        else:
            sv = SkillVector(
                user_id=user_id,
                skills=skills,
                sample_size=len(submissions),
            )
            session.add(sv)

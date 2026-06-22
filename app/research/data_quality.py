from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.contest import Contest
from app.models.ingestion import IngestionJob, IngestionJobItem
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.research import DataQualityReport
from app.models.submission import Submission
from app.models.user import User

logger = logging.getLogger("research.data_quality")


class DataQualityRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run(self) -> dict[str, Any]:
        async with self._sf() as session:
            total_users = await self._count(session, User)
            total_ratings = await self._count(session, RatingHistory)
            total_subs = await self._count(session, Submission)
            total_contests = await self._count(session, Contest)

            users_with_ratings = await self._count_with_expr(
                session, User, User.id.in_(
                    select(RatingHistory.user_id).distinct()
                )
            )
            missing_rh = total_users - users_with_ratings

            users_with_subs = await self._count_with_expr(
                session, User, User.id.in_(
                    select(Submission.user_id).distinct()
                )
            )

            users_missing_subs = total_users - users_with_subs

            orphan_subs = await self._count_orphan_submissions(session)

            duplicate_users = await self._count_duplicates(session, User, User.cf_handle)
            duplicate_contests = await self._count_duplicates(session, Contest, Contest.contest_id)

            incomplete_jobs = await self._count_incomplete_jobs(session)

            penalties = 0.0
            penalties += missing_rh * 2.0
            penalties += users_missing_subs * 1.0
            penalties += orphan_subs * 0.5
            penalties += duplicate_users * 3.0
            penalties += duplicate_contests * 2.0
            penalties += incomplete_jobs * 5.0

            max_penalty = max(total_users * 10, 100)
            base_score = 100.0
            quality_score = max(0.0, base_score - (penalties / max_penalty * base_score))
            quality_score = round(quality_score, 2)

            report = DataQualityReport(
                quality_score=quality_score,
                total_users=total_users,
                missing_rating_histories=missing_rh,
                missing_contests=0,
                orphan_submissions=orphan_subs,
                duplicate_users=duplicate_users,
                duplicate_contests=duplicate_contests,
                incomplete_ingestions=incomplete_jobs,
                details={
                    "users_with_ratings": users_with_ratings,
                    "users_with_submissions": users_with_subs,
                    "total_ratings": total_ratings,
                    "total_submissions": total_subs,
                    "total_contests": total_contests,
                    "missing_submissions": users_missing_subs,
                    "penalty_breakdown": {
                        "missing_rating_histories": round(missing_rh * 2.0, 1),
                        "missing_submissions": round(users_missing_subs * 1.0, 1),
                        "orphan_submissions": round(orphan_subs * 0.5, 1),
                        "duplicate_users": round(duplicate_users * 3.0, 1),
                        "duplicate_contests": round(duplicate_contests * 2.0, 1),
                        "incomplete_jobs": round(incomplete_jobs * 5.0, 1),
                    },
                },
            )
            session.add(report)
            await session.commit()

        logger.info(
            "Data quality: score=%.1f%% users=%d rh_missing=%d orphans=%d dup_users=%d",
            quality_score, total_users, missing_rh, orphan_subs, duplicate_users,
        )
        return {
            "quality_score": quality_score,
            "total_users": total_users,
            "missing_rating_histories": missing_rh,
            "orphan_submissions": orphan_subs,
            "duplicate_users": duplicate_users,
            "duplicate_contests": duplicate_contests,
            "incomplete_ingestions": incomplete_jobs,
        }

    async def _count(self, session: AsyncSession, model: type[Any]) -> int:
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar_one() or 0

    async def _count_with_expr(
        self, session: AsyncSession, model: type[Any], expr: Any
    ) -> int:
        result = await session.execute(
            select(func.count()).select_from(model).where(expr)
        )
        return result.scalar_one() or 0

    async def _count_orphan_submissions(self, session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count()).select_from(Submission).where(
                Submission.user_id.notin_(
                    select(User.id)
                )
            )
        )
        return result.scalar_one() or 0

    async def _count_duplicates(
        self, session: AsyncSession, model: type[Any], column: Any
    ) -> int:
        subq = (
            select(column)
            .group_by(column)
            .having(func.count() > 1)
        ).subquery()
        result = await session.execute(
            select(func.count()).select_from(
                select(model).where(column.in_(select(subq.c[0]))).subquery()
            )
        )
        return result.scalar_one() or 0

    async def _count_incomplete_jobs(self, session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count()).select_from(IngestionJob).where(
                IngestionJob.status.in_(["running", "pending"])
            )
        )
        return result.scalar_one() or 0

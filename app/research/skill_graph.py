from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import TagTransition

logger = logging.getLogger("research.skill_graph")


class SkillGraphBuilder:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def run(self) -> dict[str, Any]:
        logger.info("Building skill graph from submission history")

        raw_transitions: list[tuple[str, str, int, float, float, float]] = []
        user_set: dict[tuple[str, str], set[int]] = defaultdict(set)
        rating_gains: dict[tuple[str, str], list[float]] = defaultdict(list)
        source_ratings: dict[tuple[str, str], list[float]] = defaultdict(list)
        target_ratings: dict[tuple[str, str], list[float]] = defaultdict(list)

        async with self._sf() as session:
            conn = await session.connection()
            await conn.exec_driver_sql("SET statement_timeout = '300000'")

            user_ids = (await session.execute(
                select(text("DISTINCT user_id")).select_from(text("submissions"))
            )).scalars().all()
            logger.info("Processing %d users for skill graph", len(user_ids))

            for uid in user_ids:
                rows = (
                    await session.execute(
                        text(
                            "SELECT problem_tags, problem_rating, submission_time "
                            "FROM submissions "
                            "WHERE user_id = :uid AND verdict = 'OK' "
                            "AND problem_tags IS NOT NULL "
                            "ORDER BY submission_time"
                        ),
                        {"uid": uid},
                    )
                ).all()

                if len(rows) < 2:
                    continue

                prev_tags = rows[0][0] or []
                prev_rating = rows[0][1] or 0

                for i in range(1, len(rows)):
                    cur_tags = rows[i][0] or []
                    cur_rating = rows[i][1] or 0

                    for st in prev_tags:
                        for tt in cur_tags:
                            key = (st, tt)
                            user_set[key].add(uid)
                            gain = cur_rating - prev_rating
                            rating_gains[key].append(gain)
                            source_ratings[key].append(prev_rating)
                            target_ratings[key].append(cur_rating)

                    prev_tags = cur_tags
                    prev_rating = cur_rating

            raw_transitions = [
                (st, tt, len(user_set[(st, tt)]), len(rating_gains[(st, tt)]),
                 sum(rating_gains[(st, tt)]) / len(rating_gains[(st, tt)]),
                 sum(source_ratings[(st, tt)]) / len(source_ratings[(st, tt)]),
                 sum(target_ratings[(st, tt)]) / len(target_ratings[(st, tt)]))
                for (st, tt), users in user_set.items()
            ]

            logger.info("Found %d tag-to-tag transitions", len(raw_transitions))

            await session.execute(text("DELETE FROM tag_transitions"))

            for st, tt, uc, tc, avg_gain, avg_src, avg_tgt in raw_transitions:
                session.add(TagTransition(
                    source_tag=st, target_tag=tt,
                    transition_count=tc, user_count=uc,
                    avg_rating_gain=round(avg_gain, 2),
                    avg_source_rating=round(avg_src, 1),
                    avg_target_rating=round(avg_tgt, 1),
                ))
            await session.commit()

        strong = [t for t in raw_transitions if t[2] >= 3]
        logger.info("Skill graph complete: %d total edges, %d with >=3 users",
                     len(raw_transitions), len(strong))
        return {
            "total_edges": len(raw_transitions),
            "strong_edges": len(strong),
            "users_processed": len(user_ids),
        }

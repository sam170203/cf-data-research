from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import UserEmbedding
from app.research.features import FeatureComputer, ALL_TAGS, TAG_COLUMNS

logger = logging.getLogger("research.embeddings")


class UserEmbeddingComputer:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def compute_all(self) -> int:
        fc = FeatureComputer(self._sf)
        df = await fc.build_feature_matrix(include_labels=False)

        async with self._sf() as session:
            await session.execute(delete(UserEmbedding))
            await session.commit()

        count = 0
        for _, row in df.iterrows():
            try:
                embedding = self._build_embedding(row)
                async with self._sf() as session:
                    session.add(UserEmbedding(
                        user_id=int(row["user_id"]),
                        handle=str(row.get("handle", "")),
                        current_rating=int(row.get("current_rating", 0)),
                        max_rating=int(row.get("max_rating", 0)),
                        embedding=embedding,
                    ))
                    await session.commit()
                count += 1
            except Exception as e:
                logger.warning("Embedding error for user %s: %s", row.get("handle"), e)

        logger.info("Computed embeddings for %d users", count)
        return count

    def _build_embedding(self, row: dict[str, Any]) -> dict[str, float]:
        e: dict[str, float] = {}

        for key in [
            "total_submissions", "total_solved", "submissions_per_day", "active_days",
            "max_inactivity_streak", "median_inactivity_gap",
            "total_contests", "avg_contest_delta", "rating_volatility",
            "first_rating", "rating_gain_total", "peak_rating",
            "max_win_streak", "max_loss_streak",
            "tag_diversity", "hardest_solved_tag_rating", "avg_solved_rating",
            "growth_velocity", "growth_acceleration", "rating_volatility_recent",
            "contests_last_90d",
            "activity_last_30d", "activity_last_60d", "activity_last_90d",
            "solved_last_30d", "solved_last_60d", "solved_last_90d",
        ]:
            val = row.get(key, 0)
            val = 0.0 if val is None or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))) else float(val)
            e[key] = val

        for tag_col in TAG_COLUMNS:
            val = row.get(tag_col, 0)
            val = 0.0 if val is None or (isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf'))) else float(val)
            e[tag_col] = val

        return e

    async def update_clustering(self, user_id: int, label: int, name: str) -> None:
        async with self._sf() as session:
            emb = await session.execute(
                select(UserEmbedding).where(UserEmbedding.user_id == user_id)
            )
            emb = emb.scalar_one_or_none()
            if emb:
                emb.cluster_label = label
                emb.cluster_name = name
                await session.commit()

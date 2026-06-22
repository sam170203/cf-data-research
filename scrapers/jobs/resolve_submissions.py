from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine

logger = logging.getLogger("resolve_submissions")


async def resolve_submission_problems() -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(text("""
            UPDATE submissions s
            SET
                problem_rating = p.rating,
                problem_tags = p.tags
            FROM problems p
            WHERE s.contest_id = p.contest_id
              AND s.problem_index = p.index
              AND (s.problem_rating IS DISTINCT FROM p.rating
                   OR s.problem_tags IS DISTINCT FROM p.tags)
        """))
        await session.commit()
        updated = result.rowcount
        logger.info("Updated %d submissions from problems table", updated)

    async with session_factory() as session:
        result = await session.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE problem_rating IS NULL) AS no_rating,
                COUNT(*) FILTER (WHERE problem_tags IS NULL) AS no_tags
            FROM submissions
        """))
        row = result.one()
        logger.info(
            "After resolve: total=%d, no_rating=%d, no_tags=%d",
            row[0], row[1], row[2],
        )

    await engine.dispose()


async def main_async() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    await resolve_submission_problems()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine
from app.models.contest import Contest
from app.models.problem import Problem
from app.services.codeforces import CodeforcesClient
from scrapers.codeforces.ingest import ingest_contests, ingest_problems

logger = logging.getLogger("backfill_contests_problems")


async def backfill() -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    client = CodeforcesClient()

    try:
        async with session_factory() as session:
            contest_count = (await session.execute(
                select(func.count()).select_from(Contest)
            )).scalar_one() or 0
            problem_count = (await session.execute(
                select(func.count()).select_from(Problem)
            )).scalar_one() or 0
            logger.info("Current state: %d contests, %d problems", contest_count, problem_count)

        async with session_factory() as session:
            new_contests = await ingest_contests(client, session)
            logger.info("Ingested %d new contests", new_contests)

        async with session_factory() as session:
            new_problems = await ingest_problems(client, session)
            logger.info("Ingested %d new problems", new_problems)

        async with session_factory() as session:
            contest_count = (await session.execute(
                select(func.count()).select_from(Contest)
            )).scalar_one() or 0
            problem_count = (await session.execute(
                select(func.count()).select_from(Problem)
            )).scalar_one() or 0
            tag_rows = (await session.execute(
                select(Problem.tags).where(Problem.tags.isnot(None)).limit(1)
            )).scalar_one_or_none()
            has_tags = tag_rows is not None

            logger.info(
                "After backfill: %d contests, %d problems, tags=%s",
                contest_count, problem_count, has_tags,
            )

    finally:
        await client.close()
        await engine.dispose()


async def main_async() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    await backfill()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

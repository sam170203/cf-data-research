"""
Ingest a single Codeforces user's data.

Usage:
    python -m scrapers.jobs.ingest_user <handle>
"""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine
from app.services.codeforces import CodeforcesClient
from scrapers.codeforces.ingest import ingest_all_user_data


async def ingest_single_user(handle: str) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        client = CodeforcesClient()
        try:
            result = await ingest_all_user_data(client, session, handle)
            if result["status"] == "success":
                print(f"Successfully collected {handle}")
                print(f"  Rating: {result['current_rating']}")
                print(f"  Rating history entries: {result['rating_histories_count']}")
                print(f"  Submissions: {result['submissions_count']}")
            else:
                print(f"Failed: {result.get('reason', 'unknown')}")
        finally:
            await client.close()
            await engine.dispose()


async def main_async() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scrapers.jobs.ingest_user <handle>")
        sys.exit(1)

    handle = sys.argv[1]
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    await ingest_single_user(handle)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

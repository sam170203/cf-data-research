from __future__ import annotations

import asyncio
import logging
import sys
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine
from app.models.user import User
from app.services.codeforces import CodeforcesClient
from scrapers.codeforces.ingest import ingest_all_user_data

logger = logging.getLogger("expand_dataset")

HISTORIC_HANDLES = [
    "tourist", "Petr", "rng_58", "Egor", "ACRush", "pajenegod",
    "aryan", "orz", "hos.lyric", "dzhulgakov", "vepifanov",
    "JOHNKRAM", "Burunduk1", "eatmore", "scott_wu", "ecnerwala",
    "tmwilliamlin", "Errichto", "SecondThread",
]


async def expand(target: int = 200) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    client = CodeforcesClient()

    try:
        async with session_factory() as session:
            existing = set(
                (await session.execute(select(User.cf_handle))).scalars().all()
            )
        logger.info("Starting expansion: have %d users, target %d", len(existing), target)

        # Fetch many top handles
        all_handles = await _fetch_many_top_handles(client, target * 2)

        # Add historic handles not already in list
        for h in HISTORIC_HANDLES:
            if h not in all_handles:
                all_handles.append(h)

        # Filter out existing
        to_collect = [h for h in all_handles if h not in existing]
        to_collect = to_collect[:target]
        logger.info("Will collect %d new users (from %d candidates)", len(to_collect), len(all_handles))

        if not to_collect:
            logger.warning("No new users to collect")
            return

        start_time = time.time()
        success = 0
        failed = 0

        for idx, handle in enumerate(to_collect, 1):
            elapsed = time.time() - start_time
            rate = idx / elapsed if elapsed > 0 else 0
            remaining = (len(to_collect) - idx) / rate if rate > 0 else 0

            async with session_factory() as session:
                try:
                    result = await ingest_all_user_data(client, session, handle)
                    if result.get("status") == "success":
                        success += 1
                        logger.info(
                            "[%d/%d] %s ✓ (%d subs, %d contests, %d problems) "
                            "ETA: %dm",
                            idx, len(to_collect), handle,
                            result.get("submissions_count", 0),
                            result.get("rating_histories_count", 0),
                            result.get("problems_count", 0),
                            int(remaining / 60),
                        )
                    else:
                        failed += 1
                        logger.warning(
                            "[%d/%d] %s ✗ (%s)",
                            idx, len(to_collect), handle, result.get("reason"),
                        )
                except Exception as e:
                    failed += 1
                    logger.warning("[%d/%d] %s ✗ %s", idx, len(to_collect), handle, e)

        async with session_factory() as session:
            total = (await session.execute(
                select(User).order_by(User.id.desc()).limit(1)
            )).scalar_one_or_none()
            logger.info(
                "Expansion complete: %d new (%d ok, %d failed). Total users now ~%d",
                len(to_collect), success, failed,
                (await session.execute(select(User.cf_handle))).scalars().all(),
            )

    finally:
        await client.close()
        await engine.dispose()


async def _fetch_many_top_handles(client: CodeforcesClient, count: int) -> list[str]:
    try:
        result = await client._request(
            "GET", "/user.ratedList",
            params={"activeOnly": "true", "includeRetired": "false"},
        )
        if isinstance(result, list):
            return [u["handle"] for u in result if u.get("handle")][:count]
    except Exception as e:
        logger.warning("Failed to fetch rated list: %s", e)
    return []


async def main_async() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    await expand(target=target)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

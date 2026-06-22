from __future__ import annotations

import argparse
import asyncio
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine
from app.models.ingestion import IngestionJob, IngestionJobItem
from app.models.research import CollectionCheckpoint
from app.services.codeforces import CodeforcesClient
from app.services.ingestion import IngestionJobManager
from scrapers.codeforces.ingest import ingest_all_user_data

logger = logging.getLogger("collect_top_users")

HISTORIC_HANDLES = [
    "tourist", "Petr", "rng_58", "Egor", "ACRush",
    "pajenegod", "aryan", "orz", "hos.lyric", "dzhulgakov",
    "vepifanov", "JOHNKRAM", "Burunduk1", "eatmore", "scott_wu",
    "ecnerwala", "tmwilliamlin", "Errichto", "SecondThread",
]


async def collect_top_users(
    target_count: int = 100,
    include_historic: bool = False,
    resume: bool = False,
) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    if resume:
        async with session_factory() as session:
            cp = (
                await session.execute(
                    select(CollectionCheckpoint).where(
                        CollectionCheckpoint.loop_name == "data_acquisition"
                    )
                )
            ).scalar_one_or_none()
            skip_handles: set[str] = set()
            if cp and cp.last_handle:
                skip_handles.add(cp.last_handle)
    else:
        skip_handles = set()

    async with session_factory() as session:
        job_mgr = IngestionJobManager(session)
        job = await job_mgr.create_job("top_users_collection", total_items=target_count)
        print(f"Created job {job.id}")

    client = CodeforcesClient()

    try:
        handles = await _fetch_top_handles(client, target_count)
        if include_historic:
            for h in HISTORIC_HANDLES:
                if h not in handles:
                    handles.append(h)

        if skip_handles:
            handles = [h for h in handles if h not in skip_handles]
            print(f"Resuming: skipping {len(skip_handles)} already-collected handles")

        async with session_factory() as session:
            job_mgr = IngestionJobManager(session)
            await job_mgr.start_job(job.id)
            refreshed = await session.get(IngestionJob, job.id)
            if refreshed is None:
                raise RuntimeError(f"Job {job.id} not found")
            job = refreshed
            job.total_items = len(handles)
            await session.commit()
            items = await job_mgr.add_items(job.id, handles)

        start_time = time.time()
        for idx, handle in enumerate(handles, 1):
            async with session_factory() as session:
                item_map = {item.item_identifier: item for item in items}
                item = item_map.get(handle)
                if not item:
                    continue

                item_job_mgr = IngestionJobManager(session)
                await item_job_mgr.mark_item_running(item.id)
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                remaining = (len(handles) - idx) / rate if rate > 0 else 0

                try:
                    result = await ingest_all_user_data(client, session, handle)
                    status = result.get("status", "failed")

                    if status == "success":
                        await item_job_mgr.mark_item_completed(item.id)
                        print(
                            f"[{idx}/{len(handles)}] {handle} "
                            f"✓ ({result.get('submissions_count', 0)} subs, "
                            f"{result.get('rating_histories_count', 0)} contests)"
                        )
                    else:
                        reason = result.get("reason", "unknown")
                        await item_job_mgr.mark_item_failed(item.id, error=reason)
                        print(f"[{idx}/{len(handles)}] {handle} ✗ ({reason})")

                except Exception as e:
                    logger.exception("Unexpected error collecting %s", handle)
                    await item_job_mgr.mark_item_failed(item.id, error=str(e))
                    print(f"[{idx}/{len(handles)}] {handle} ✗ ({e})")

                if resume:
                    cp = (
                        await session.execute(
                            select(CollectionCheckpoint).where(
                                CollectionCheckpoint.loop_name == "data_acquisition"
                            )
                        )
                    ).scalar_one_or_none()
                    if cp:
                        from app.models.user import User
                        user = (
                            await session.execute(
                                select(User).where(User.cf_handle == handle)
                            )
                        ).scalar_one_or_none()
                        if user:
                            user_id = user.id
                        else:
                            user_id = None
                        cp.last_handle = handle
                        cp.last_user_id = user_id
                        cp.total_processed = idx
                        cp.updated_at = __import__("datetime").datetime.now(
                            __import__("datetime").UTC
                        )
                        await session.commit()

                progress = await item_job_mgr.get_job_progress(job.id)
                pct = progress.get("progress_percent", 0)
                eta_m = max(0, int(remaining / 60))
                print(
                    f"  Progress: {pct}%  "
                    f"ETA: {eta_m}m remaining  "
                    f"({progress['completed_items']} ok, "
                    f"{progress['failed_items']} failed)"
                )

        async with session_factory() as session:
            job_mgr = IngestionJobManager(session)
            await job_mgr.complete_job(job.id)

        print(f"\nCollection complete. Job {job.id} finished.")

    except Exception:
        logger.exception("Collection failed")
        async with session_factory() as session:
            job_mgr = IngestionJobManager(session)
            await job_mgr.fail_job(job.id)
        raise
    finally:
        await client.close()


async def _fetch_top_handles(client: CodeforcesClient, count: int) -> list[str]:
    handles: list[str] = []
    try:
        result = await client._request(
            "GET",
            "/user.ratedList",
            params={"activeOnly": "true", "includeRetired": "false"},
        )
    except Exception as e:
        logger.warning("Failed to fetch rated list: %s", e)
        return handles

    if not isinstance(result, list):
        return handles

    for user_data in result:
        handle = user_data.get("handle")
        if handle and handle not in handles:
            handles.append(handle)
            if len(handles) >= count:
                break

    return handles[:count]


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Collect top Codeforces users")
    parser.add_argument(
        "--count", type=int, default=settings.top_user_target_count,
    )
    parser.add_argument("--historic", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    await collect_top_users(
        target_count=args.count,
        include_historic=args.historic,
        resume=args.resume,
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

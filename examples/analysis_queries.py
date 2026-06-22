"""
Example: Run analysis queries against the database.

Usage:
  uv run python examples/analysis_queries.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import engine
from app.services.analysis import (
    get_fastest_growth_users,
    get_tag_distribution_by_rating_bucket,
    get_users_reaching_rating,
)


async def main() -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Users who reached Expert (1600+)
        print("=" * 60)
        print("Users who reached Expert (1600+):")
        df = await get_users_reaching_rating(session, 1600)
        if not df.empty:
            print(df.head(10).to_string(index=False))
        else:
            print("  (no data yet — run collect_top_users first)")
        print()

        # 2. Tag distribution
        print("=" * 60)
        print("Tag distribution by rating bucket:")
        df_tags = await get_tag_distribution_by_rating_bucket(session)
        if not df_tags.empty:
            print(df_tags.to_string(index=False))
        else:
            print("  (no data yet)")
        print()

        # 3. Fastest growth users
        print("=" * 60)
        print("Fastest growth users (top 20):")
        df_growth = await get_fastest_growth_users(session, min_contests=3)
        if not df_growth.empty:
            print(df_growth.head(20).to_string(index=False))
        else:
            print("  (no data yet)")
        print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

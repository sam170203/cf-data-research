"""
Example: Collect a user's data and run basic analysis.

This script demonstrates the full data pipeline:
  1. Ingest a user's data from Codeforces
  2. Run analysis queries against the database

Prerequisites:
  - PostgreSQL running with the schema applied
  - Environment variables set (or .env file)

Usage:
  uv run python examples/collect_and_analyze.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import engine
from app.services.codeforces import CodeforcesClient
from scrapers.codeforces.ingest import ingest_all_user_data


async def main() -> None:
    handle = "tourist"  # Change this to any CF handle

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        client = CodeforcesClient()
        try:
            print(f"Collecting data for {handle}...")
            result = await ingest_all_user_data(client, session, handle)

            if result["status"] == "success":
                print(f"\n{'='*50}")
                print(f"User: {handle}")
                print(f"Current Rating: {result['current_rating']}")
                print(f"Rating History Entries: {result['rating_histories_count']}")
                print(f"Submissions Collected: {result['submissions_count']}")
                print(f"{'='*50}\n")
            else:
                print(f"Failed: {result.get('reason', 'unknown')}")

        finally:
            await client.close()
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

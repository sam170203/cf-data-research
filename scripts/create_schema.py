"""
Standalone script to create the database schema directly (without Alembic).

Useful for initial setup or testing without running migrations.

Usage:
    uv run python scripts/create_schema.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.base import Base
from app.db.session import engine


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Schema created successfully.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_schema())

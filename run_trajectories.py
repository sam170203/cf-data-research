"""Run trajectory discovery with optimized session management."""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger("run_trajectories")

from app.db.session import async_sessionmaker, engine as db_engine
from app.research.trajectories import TrajectoryAnalyzer


async def main():
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    ta = TrajectoryAnalyzer(sf)
    results = await ta.discover_all()

    for milestone, data in results.items():
        users = data.get("users", [])
        if isinstance(users, list):
            print(f"  {milestone}: {len(users)} users")
        else:
            print(f"  {milestone}: {users} events")


asyncio.run(main())

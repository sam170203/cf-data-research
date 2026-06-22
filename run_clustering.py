"""Run clustering with optimized session management."""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("run_clustering")

from app.db.session import async_sessionmaker, engine as db_engine
from app.research.clustering import ClusteringEngine


async def main():
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    ce = ClusteringEngine(sf)
    result = await ce.run_all()
    logger.info("Clustering result: %s", result)

    # Print summary
    for run in result.get("runs", []):
        print(f"  {run['algorithm']}: {run['n_clusters']} clusters, sil={run['silhouette']}")
        for c in run.get("clusters", []):
            print(f"    {c['label']}: {c['name']} ({c['n_users']} users, avg_rating={c['avg_rating']})")


asyncio.run(main())

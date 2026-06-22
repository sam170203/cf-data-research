"""Compute embeddings for all users using cached feature matrix."""
import asyncio
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("run_embeddings")

from sqlalchemy import text

from app.db.session import async_sessionmaker, engine
from app.research.features import FeatureComputer
from app.research.embeddings import UserEmbeddingComputer


async def main():
    sf = async_sessionmaker(engine, expire_on_commit=False)

    fc = FeatureComputer(sf)
    df = await fc.build_feature_matrix(include_labels=False)
    logger.info("Loaded feature matrix: %d rows, %d cols", len(df), len(df.columns))

    computer = UserEmbeddingComputer(sf)

    # Build all embeddings first (no DB calls)
    records = []
    for idx, row in df.iterrows():
        try:
            emb = computer._build_embedding(row)
            records.append({
                "user_id": int(row["user_id"]),
                "handle": str(row.get("handle", "")),
                "current_rating": int(row.get("current_rating", 0)),
                "max_rating": int(row.get("max_rating", 0)),
                "embedding": json.dumps(emb),
            })
        except Exception as e:
            logger.warning("Build error for user %s: %s", row.get("handle"), e)

    logger.info("Built %d records", len(records))

    async with sf() as session:
        await session.execute(text("TRUNCATE TABLE user_embeddings RESTART IDENTITY CASCADE"))
        await session.commit()
        logger.info("Truncated user_embeddings")

    async with sf() as session:
        insert_sql = text("""
            INSERT INTO user_embeddings (user_id, handle, current_rating, max_rating, embedding)
            VALUES (:user_id, :handle, :current_rating, :max_rating, CAST(:embedding AS jsonb))
        """)

        for i, rec in enumerate(records):
            await session.execute(insert_sql, rec)
            if (i + 1) % 50 == 0:
                await session.flush()
                logger.info("Inserted %d/%d", i + 1, len(records))

        await session.flush()
        await session.commit()
        logger.info("Done: %d embeddings", len(records))


asyncio.run(main())

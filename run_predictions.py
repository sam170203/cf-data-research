"""Run prediction pipeline to generate plateau/prediction data."""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("run_predictions")

from app.db.session import async_sessionmaker, engine as db_engine
from app.research.predictor import Predictor


async def main():
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    predictor = Predictor(sf)
    results = await predictor.run_full_pipeline()
    logger.info("Prediction pipeline complete")
    print(predictor.get_model_summary(results))


asyncio.run(main())

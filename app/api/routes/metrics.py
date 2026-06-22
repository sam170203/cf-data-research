from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.services.cache import get_cache_stats
from app.models.contest import Contest
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User
from app.schemas.metrics import MetricsResponse, ResearchStatusResponse

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(db: AsyncSession = Depends(get_db)) -> MetricsResponse:
    async def count(model: type[Any]) -> int:
        result = await db.execute(select(func.count()).select_from(model))
        return result.scalar_one() or 0

    return MetricsResponse(
        users=await count(User),
        rating_histories=await count(RatingHistory),
        submissions=await count(Submission),
        contests=await count(Contest),
        problems=await count(Problem),
    )


@router.get("/cache/stats")
async def cache_stats() -> dict[str, Any]:
    return get_cache_stats()


@router.get("/research-status", response_model=ResearchStatusResponse)
async def get_research_status(db: AsyncSession = Depends(get_db)) -> ResearchStatusResponse:
    result = await db.execute(
        select(func.count(User.id)).where(User.current_rating.isnot(None))
    )
    collected = result.scalar_one()
    target = settings.top_user_target_count
    coverage = round(collected / target * 100, 1) if target > 0 else 0.0

    if coverage == 0:
        status = "not_started"
    elif coverage < 100:
        status = "collecting"
    else:
        status = "complete"

    return ResearchStatusResponse(
        top_users_collected=collected,
        target_top_users=target,
        coverage_percent=coverage,
        dataset_status=status,
    )

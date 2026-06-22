from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/top-users")
async def get_top_users(
    limit: int = 100, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(User)
        .order_by(User.current_rating.desc().nullslast())
        .limit(limit)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "cf_handle": u.cf_handle,
            "current_rating": u.current_rating,
            "max_rating": u.max_rating,
            "rank": u.rank,
            "max_rank": u.max_rank,
            "country": u.country,
            "organization": u.organization,
        }
        for u in users
    ]


@router.get("/rating-distribution")
async def get_rating_distribution(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    buckets = [
        (0, 1199), (1200, 1399), (1400, 1599), (1600, 1899),
        (1900, 2199), (2200, 3000), (3000, 4000),
    ]
    labels = [
        "<1200", "1200-1399", "1400-1599", "1600-1899",
        "1900-2199", "2200-3000", "3000+",
    ]
    distribution = []
    total = await db.execute(select(func.count(User.id)))
    total_users = total.scalar_one()
    for (lo, hi), label in zip(buckets, labels):
        result = await db.execute(
            select(func.count(User.id)).where(
                User.current_rating >= lo, User.current_rating <= hi
            )
        )
        count = result.scalar_one()
        distribution.append({
            "bucket": label,
            "count": count,
            "percentage": round(count / total_users * 100, 2) if total_users > 0 else 0,
        })
    return {"distribution": distribution, "total_users": total_users}


@router.get("/tag-distribution")
async def get_tag_distribution(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    from app.models.submission import Submission

    result = await db.execute(
        select(
            Submission.problem_tags,
            func.count(Submission.id).label("count"),
        )
        .where(
            Submission.problem_tags.isnot(None),
            Submission.verdict == "OK",
        )
        .group_by(Submission.problem_tags)
        .order_by(func.count(Submission.id).desc())
        .limit(50)
    )
    rows = result.all()
    tags_total: dict[str, int] = {}
    for row in rows:
        tags = row[0]
        count_val: int = row[1] or 0
        if tags:
            for tag in tags:
                tags_total[tag] = tags_total.get(tag, 0) + count_val
    sorted_tags = sorted(
        tags_total.items(), key=lambda x: x[1], reverse=True
    )[:30]
    return {
        "tags": [{"tag": k, "count": v} for k, v in sorted_tags]
    }

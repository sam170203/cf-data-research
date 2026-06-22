from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.submission import Submission
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{handle}/summary")
async def get_user_summary(handle: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.rating_histories))
        .where(User.cf_handle == handle)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {handle} not found")

    return {
        "profile": UserResponse.model_validate(user).model_dump(),
        "rating_history": [
            {
                "contest_id": rh.contest_id,
                "contest_name": rh.contest_name,
                "old_rating": rh.old_rating,
                "new_rating": rh.new_rating,
                "rating_change": rh.rating_change,
                "contest_time": rh.contest_time.isoformat(),
            }
            for rh in sorted(user.rating_histories, key=lambda x: x.contest_time)
        ],
        "stats": await _compute_user_stats(user.id, db),
    }


async def _compute_user_stats(user_id: int, db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        select(Submission).where(Submission.user_id == user_id)
    )
    submissions = result.scalars().all()

    total = len(submissions)
    solved = sum(1 for s in submissions if s.verdict == "OK")
    langs: dict[str, int] = {}
    for s in submissions:
        if s.programming_language:
            langs[s.programming_language] = langs.get(s.programming_language, 0) + 1
    verdicts: dict[str, int] = {}
    for s in submissions:
        verdicts[s.verdict or "UNKNOWN"] = verdicts.get(s.verdict or "UNKNOWN", 0) + 1

    return {
        "total_submissions": total,
        "solved_problems": solved,
        "solve_rate": round(solved / total * 100, 2) if total > 0 else 0,
        "languages": sorted(langs.items(), key=lambda x: -x[1]),
        "verdicts": verdicts,
    }

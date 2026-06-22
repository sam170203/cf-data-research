from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.ingestion import IngestionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    limit: int = 20, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
    )
    jobs = result.scalars().all()
    return [
        {
            "job_id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "total_items": j.total_items,
            "completed_items": j.completed_items,
            "failed_items": j.failed_items,
            "progress_percent": _calc_progress(j),
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.get("/{job_id}")
async def get_job_detail(job_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    result = await db.execute(
        select(IngestionJob)
        .options(selectinload(IngestionJob.items))
        .where(IngestionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return {"error": "Job not found"}
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "total_items": job.total_items,
        "completed_items": job.completed_items,
        "failed_items": job.failed_items,
        "progress_percent": _calc_progress(job),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "items": [
            {
                "id": item.id,
                "item_identifier": item.item_identifier,
                "status": item.status,
                "error_message": item.error_message,
            }
            for item in job.items
        ],
    }


def _calc_progress(job: IngestionJob) -> float:
    if job.total_items == 0:
        return 0.0
    return round((job.completed_items + job.failed_items) / job.total_items * 100, 1)

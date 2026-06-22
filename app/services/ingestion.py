from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import IngestionJob, IngestionJobItem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User

logger = logging.getLogger(__name__)


class IngestionJobManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(
        self, job_type: str, total_items: int = 0
    ) -> IngestionJob:
        job = IngestionJob(
            job_type=job_type,
            status="pending",
            total_items=total_items,
            completed_items=0,
            failed_items=0,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def start_job(self, job_id: int) -> None:
        job = await self.session.get(IngestionJob, job_id)
        if job:
            job.status = "running"
            job.started_at = datetime.now(UTC)
            await self.session.commit()

    async def complete_job(self, job_id: int) -> None:
        job = await self.session.get(IngestionJob, job_id)
        if job:
            job.status = "completed"
            job.finished_at = datetime.now(UTC)
            await self.session.commit()

    async def fail_job(self, job_id: int) -> None:
        job = await self.session.get(IngestionJob, job_id)
        if job:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            await self.session.commit()

    async def add_items(
        self, job_id: int, identifiers: list[str]
    ) -> list[IngestionJobItem]:
        items = [
            IngestionJobItem(
                job_id=job_id,
                item_identifier=identifier,
                status="pending",
            )
            for identifier in identifiers
        ]
        self.session.add_all(items)
        await self.session.commit()
        for item in items:
            await self.session.refresh(item)
        return items

    async def mark_item_completed(self, item_id: int) -> None:
        item = await self.session.get(IngestionJobItem, item_id)
        if item:
            item.status = "completed"
            await self._update_job_counts(item.job_id)
            await self.session.commit()

    async def mark_item_failed(self, item_id: int, error: str = "") -> None:
        item = await self.session.get(IngestionJobItem, item_id)
        if item:
            item.status = "failed"
            item.error_message = error
            await self._update_job_counts(item.job_id)
            await self.session.commit()

    async def mark_item_running(self, item_id: int) -> None:
        item = await self.session.get(IngestionJobItem, item_id)
        if item:
            item.status = "running"
            await self.session.commit()

    async def _update_job_counts(self, job_id: int) -> None:
        job = await self.session.get(IngestionJob, job_id)
        if not job:
            return
        completed = await self._count_items_by_status(job_id, "completed")
        failed = await self._count_items_by_status(job_id, "failed")
        job.completed_items = completed
        job.failed_items = failed
        if completed + failed >= job.total_items:
            job.status = "completed"
            job.finished_at = datetime.now(UTC)

    async def _count_items_by_status(self, job_id: int, status: str) -> int:
        result = await self.session.execute(
            select(func.count(IngestionJobItem.id)).where(
                IngestionJobItem.job_id == job_id,
                IngestionJobItem.status == status,
            )
        )
        return result.scalar_one()

    async def get_job_progress(self, job_id: int) -> dict[str, Any]:
        job = await self.session.get(IngestionJob, job_id)
        if not job:
            return {}
        completed = await self._count_items_by_status(job_id, "completed")
        failed = await self._count_items_by_status(job_id, "failed")
        total = job.total_items
        progress = ((completed + failed) / total * 100) if total > 0 else 0
        return {
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "total_items": total,
            "completed_items": completed,
            "failed_items": failed,
            "progress_percent": round(progress, 1),
        }


async def get_metrics(session: AsyncSession) -> dict[str, int]:
    metrics = {}
    for table, model in [
        ("users", User),
        ("rating_histories", RatingHistory),
        ("submissions", Submission),
    ]:
        result = await session.execute(select(func.count()).select_from(model))
        metrics[table] = result.scalar_one()
    return metrics

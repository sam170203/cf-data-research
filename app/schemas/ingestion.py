from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    progress_percent: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class IngestionJobItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    item_identifier: str
    status: str
    error_message: str | None = None


class IngestionJobDetailResponse(IngestionJobResponse):
    items: list[IngestionJobItemResponse] = []

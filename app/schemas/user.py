from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cf_handle: str
    current_rating: int | None = None
    max_rating: int | None = None
    rank: str | None = None
    max_rank: str | None = None
    country: str | None = None
    organization: str | None = None
    first_seen_at: datetime
    updated_at: datetime


class UserSummary(BaseModel):
    cf_handle: str
    current_rating: int | None = None
    max_rating: int | None = None
    rank: str | None = None
    max_rank: str | None = None

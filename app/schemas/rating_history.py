from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RatingHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    contest_id: int
    contest_name: str
    old_rating: int
    new_rating: int
    rating_change: int
    contest_time: datetime

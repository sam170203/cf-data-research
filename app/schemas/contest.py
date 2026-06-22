from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contest_id: int
    name: str
    type: str
    phase: str
    start_time: datetime | None = None
    duration: int | None = None

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    contest_id: int | None = None
    problem_index: str | None = None
    problem_name: str | None = None
    problem_rating: int | None = None
    verdict: str | None = None
    programming_language: str | None = None
    submission_time: datetime

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    users: int = 0
    rating_histories: int = 0
    submissions: int = 0
    contests: int = 0
    problems: int = 0


class ResearchStatusResponse(BaseModel):
    top_users_collected: int = 0
    target_top_users: int = 0
    coverage_percent: float = 0.0
    dataset_status: str = "not_started"

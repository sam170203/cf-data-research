from __future__ import annotations

from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "cf_growth_lab"
    database_echo: bool = False

    cf_api_base_url: str = "https://codeforces.com/api"
    cf_api_key: str = ""
    cf_api_secret: str = ""
    request_timeout: int = 30
    max_retries: int = 3
    rate_limit_per_second: float = 1.0

    top_user_target_count: int = 100
    top_user_batch_size: int = 5

    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{quote(self.db_password, safe='')}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


settings = Settings()

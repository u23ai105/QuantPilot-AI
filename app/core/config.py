from typing import Literal

from pydantic import SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "QuantPilot AI"
    database_url: str
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    log_level: str = "INFO"
    cors_origins: str | list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    #: Set false to skip installing `RateLimitMiddleware`. The test suite does this: it shares one
    #: client identity across every test, so real per-minute budgets would leak between tests.
    rate_limit_enabled: bool = True

    #: When set, `GET /metrics` requires `Authorization: Bearer <token>`. Empty means open, which is
    #: fine when the port is only reachable from inside the deployment's network (the Render setup) and
    #: is what a local Prometheus expects; set it whenever the API is exposed directly.
    metrics_token: str = ""

    # Gemini AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_temperature: float = 0.0
    gemini_max_output_tokens: int = 4096

    llm_provider: Literal["gemini", "nim"] = "gemini"
    llm_model: str | None = None
    nvidia_api_key: SecretStr = SecretStr("")
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    @field_validator("llm_provider", "llm_model", "nvidia_base_url", mode="before")
    @classmethod
    def default_empty_llm_settings(cls, value, info: ValidationInfo):
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and "asyncpg" not in v:
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v or ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

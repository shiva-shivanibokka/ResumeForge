"""Typed application settings, validated at startup.

All configuration flows through here. Importing this module never performs I/O;
call `get_settings()` (cached) to read the validated settings. The app's
lifespan calls `get_settings()` once at startup so a misconfiguration fails
loudly and immediately instead of surfacing as a confusing runtime error later.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Environment
    environment: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"

    # CORS origins. Stored as a raw CSV string (kept as `str` so pydantic-settings
    # doesn't try to JSON-decode the env value); exposed as a list via the
    # `allowed_origins` property below.
    allowed_origins_csv: str = Field("http://localhost:5173", validation_alias="ALLOWED_ORIGINS")

    # Limits / resilience
    file_ttl_seconds: int = 1800
    max_upload_mb: int = 10
    request_timeout_s: int = 60
    llm_max_retries: int = 2

    # Optional server-side provider keys (fallback when the user supplies none)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    github_token: str | None = None

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins_csv.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

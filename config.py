from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BUDGETWINGS_",
        extra="ignore",
    )

    app_name: str = "BudgetWings"
    environment: str = "development"
    user_agent: str = "BudgetWings/0.1 (+https://github.com/kingheu0818-sketch/budgetwings)"

    scraper_timeout_seconds: float = Field(default=30.0, ge=1.0)
    scraper_retry_attempts: int = Field(default=3, ge=1)
    scraper_retry_backoff_seconds: float = Field(default=1.0, ge=0.0)
    request_rate_limit_seconds: float = Field(default=1.0, ge=0.0)

    database_url: str = "sqlite:///data/budgetwings.db"
    llm_provider: Literal["claude", "openai"] = "claude"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_timeout_seconds: float = Field(default=60.0, ge=1.0)

    skyscanner_api_key: str | None = Field(default=None, validation_alias="SKYSCANNER_API_KEY")
    kiwi_api_key: str | None = Field(default=None, validation_alias="KIWI_API_KEY")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    weather_api_key: str | None = Field(default=None, validation_alias="WEATHER_API_KEY")
    exchange_rate_api_key: str | None = Field(
        default=None,
        validation_alias="EXCHANGE_RATE_API_KEY",
    )
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    tavily_api_key: str | None = Field(default=None, validation_alias="TAVILY_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()

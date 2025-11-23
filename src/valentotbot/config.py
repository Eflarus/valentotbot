from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # Telegram bot
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_username: str = Field(..., alias="BOT_USERNAME")

    # Webhook
    webhook_base_url: AnyUrl = Field(..., alias="WEBHOOK_BASE_URL")
    webhook_path: str = Field("/bot/webhook", alias="WEBHOOK_PATH")

    # Application
    app_env: AppEnv = Field(AppEnv.LOCAL, alias="APP_ENV")
    log_level: LogLevel = Field("INFO", alias="LOG_LEVEL")

    # Database (PostgreSQL)
    postgres_host: str = Field(..., alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")

    # Redis
    redis_url: str = Field(..., alias="REDIS_URL")

    # HTTP service (FastAPI / webhook listener)
    http_host: str = Field("0.0.0.0", alias="HTTP_HOST")
    http_port: int = Field(8080, alias="HTTP_PORT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

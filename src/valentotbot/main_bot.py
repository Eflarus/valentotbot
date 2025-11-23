from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram.ext import Application, ApplicationBuilder, Updater

from valentotbot.config import Settings, get_settings
from valentotbot.infrastructure.db import get_session_maker
from valentotbot.logging import setup_logging
from valentotbot.presentation.bot.handlers import register_handlers

logger = logging.getLogger(__name__)


def build_webhook_url(settings: Settings) -> str:
    """Construct full webhook URL from base and path."""
    path = settings.webhook_path
    normalized_path = path if path.startswith("/") else f"/{path}"
    base = str(settings.webhook_base_url)
    return f"{base.rstrip('/')}{normalized_path}"


async def init_db(settings: Settings) -> None:
    """Initialize database connection (placeholder for engine/session setup)."""
    logger.info(
        "Initializing database connection to %s:%s (db=%s)",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
    )


async def init_redis(settings: Settings) -> None:
    """Initialize Redis connection (placeholder for client setup)."""
    logger.info("Initializing Redis connection to %s", settings.redis_url)


async def start_webhook(application: Application, settings: Settings) -> None:
    """Start Telegram webhook listener."""
    webhook_url = build_webhook_url(settings)

    await application.initialize()
    await application.bot.set_webhook(url=webhook_url)
    await application.start()

    updater: Optional[Updater] = application.updater
    if updater is None:
        raise RuntimeError("Application updater is not initialized for webhook mode.")

    await updater.start_webhook(
        listen=settings.http_host,
        port=settings.http_port,
        url_path=settings.webhook_path,
    )
    logger.info(
        "Webhook started: listen=%s port=%s url_path=%s target_url=%s",
        settings.http_host,
        settings.http_port,
        settings.webhook_path,
        webhook_url,
    )

    await updater.idle()
    await application.stop()
    await application.shutdown()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    session_maker = get_session_maker(settings)
    await init_db(settings)
    await init_redis(settings)

    application = ApplicationBuilder().token(settings.bot_token).build()
    application.bot_data["session_maker"] = session_maker
    register_handlers(application)
    await start_webhook(application, settings)


if __name__ == "__main__":
    asyncio.run(main())

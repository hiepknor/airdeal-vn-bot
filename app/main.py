from __future__ import annotations

import asyncio
import threading

import uvicorn

from app.api import create_api
from app.bot.middleware.webhook_auth import normalize_webhook_secret
from app.bot.telegram_bot import build_app
from app.config import settings
from app.db.database import init_db
from app.utils.logging import get_logger, setup_logging


async def _startup() -> None:
    setup_logging(settings.log_level)
    log = get_logger(__name__)
    log.info("starting", mode=settings.telegram_mode)
    await init_db()


def _webhook_config() -> tuple[str, str]:
    if not settings.telegram_webhook_url:
        raise RuntimeError("TELEGRAM_WEBHOOK_URL required in webhook mode")
    try:
        secret = normalize_webhook_secret(settings.telegram_webhook_secret)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    return settings.telegram_webhook_url, secret


def _start_health_server() -> uvicorn.Server:
    config = uvicorn.Config(
        create_api(),
        host="0.0.0.0",  # noqa: S104 - container health endpoint
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="health-server", daemon=True)
    thread.start()
    return server


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_startup())
    app = build_app()
    if settings.telegram_mode == "webhook":
        webhook_url, webhook_secret = _webhook_config()
        app.run_webhook(
            listen="0.0.0.0",  # noqa: S104 - container webhook listener
            port=settings.http_port,
            webhook_url=webhook_url,
            secret_token=webhook_secret,
        )
    else:
        _start_health_server()
        app.run_polling()


if __name__ == "__main__":
    main()

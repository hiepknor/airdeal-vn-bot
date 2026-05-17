from __future__ import annotations

import asyncio

from app.bot.telegram_bot import build_app
from app.config import settings
from app.db.database import init_db
from app.utils.logging import get_logger, setup_logging


async def _startup() -> None:
    setup_logging(settings.log_level)
    log = get_logger(__name__)
    log.info("starting", mode=settings.telegram_mode)
    await init_db()


def main() -> None:
    asyncio.run(_startup())
    app = build_app()
    if settings.telegram_mode == "webhook":
        if not settings.telegram_webhook_url:
            raise RuntimeError("TELEGRAM_WEBHOOK_URL required in webhook mode")
        app.run_webhook(
            listen="0.0.0.0",
            port=settings.http_port,
            webhook_url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()

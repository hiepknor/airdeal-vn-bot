from __future__ import annotations

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.alerts.notifier import TelegramAlertNotifier
from app.alerts.scheduler import AlertScheduler
from app.alerts.service import AlertService
from app.bot.handlers import (
    cmd_alerts,
    cmd_deals,
    cmd_delete,
    cmd_help,
    cmd_history,
    cmd_pause,
    cmd_start,
    cmd_watch,
    on_alert_callback,
    on_text,
)
from app.bot.middleware.rate_limit import TokenBucketRateLimiter
from app.config import settings
from app.flights.cache import SearchCache
from app.flights.providers.base import FlightProvider
from app.flights.providers.mock import MockProvider
from app.flights.service import FlightService
from app.utils.logging import get_logger

log = get_logger(__name__)


def _build_providers() -> list[FlightProvider]:
    providers: list[FlightProvider] = []

    if settings.fast_flights_enabled:
        from app.flights.providers.fast_flights_provider import FastFlightsProvider
        providers.append(FastFlightsProvider())
        log.info("provider_enabled", name="fast_flights")

    if settings.atadi_web_enabled:
        from app.flights.providers.atadi_playwright import AtadiPlaywrightProvider
        providers.append(AtadiPlaywrightProvider(
            affiliate_id=settings.traveloka_affiliate_id,
            use_cloak=settings.atadi_use_cloak,
        ))
        log.info("provider_enabled", name="atadi_web", cloak=settings.atadi_use_cloak)

    if settings.atadi_enabled and settings.atadi_api_key:
        from app.flights.providers.atadi import AtadiProvider
        providers.append(AtadiProvider(api_key=settings.atadi_api_key))
        log.info("provider_enabled", name="atadi")

    if not providers:
        log.warning("no_real_providers_configured_using_mock")
        providers.append(MockProvider())

    return providers


async def _post_init(application: Application) -> None:
    scheduler = application.bot_data["alert_scheduler"]
    scheduler.start()


async def _post_shutdown(application: Application) -> None:
    scheduler = application.bot_data.get("alert_scheduler")
    if scheduler:
        scheduler.shutdown()


def build_app() -> Application:
    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    flight_service = FlightService(
        _build_providers(),
        cache=SearchCache(),
    )
    alert_service = AlertService()
    notifier = TelegramAlertNotifier(application.bot)
    application.bot_data["flight_service"] = flight_service
    application.bot_data["alert_service"] = alert_service
    application.bot_data["rate_limiter"] = TokenBucketRateLimiter(settings.rate_limit_per_minute)
    application.bot_data["alert_scheduler"] = AlertScheduler(alert_service, flight_service, notifier)

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("search", on_text))
    application.add_handler(CommandHandler("watch", cmd_watch))
    application.add_handler(CommandHandler("alerts", cmd_alerts))
    application.add_handler(CommandHandler("deals", cmd_deals))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("pause", cmd_pause))
    application.add_handler(CommandHandler("delete", cmd_delete))
    application.add_handler(CallbackQueryHandler(on_alert_callback, pattern=r"^(pause|delete):"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return application

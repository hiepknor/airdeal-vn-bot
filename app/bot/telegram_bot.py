from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from app.bot.handlers import cmd_help, cmd_start, on_text
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


def build_app() -> Application:
    application = ApplicationBuilder().token(settings.telegram_bot_token).build()
    application.bot_data["flight_service"] = FlightService(
        _build_providers(),
        cache=SearchCache(),
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("search", on_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return application

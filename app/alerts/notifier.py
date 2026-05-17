from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import NetworkError, RetryAfter, TimedOut
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.bot.messages import format_alert_offer
from app.flights.models import FlightOffer


class TelegramAlertNotifier:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @retry(
        retry=retry_if_exception_type((NetworkError, RetryAfter, TimedOut)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def send_alert(self, telegram_id: int, offer: FlightOffer) -> None:
        await self.bot.send_message(
            chat_id=telegram_id,
            text=format_alert_offer(offer),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

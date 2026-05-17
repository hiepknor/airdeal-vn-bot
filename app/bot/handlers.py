from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.bot import messages
from app.db.database import upsert_user
from app.flights.providers.base import AllProvidersFailed
from app.flights.service import FlightService
from app.nlp.parser import parse
from app.utils.logging import get_logger

log = get_logger(__name__)


def _service(context: ContextTypes.DEFAULT_TYPE) -> FlightService:
    return context.application.bot_data["flight_service"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await upsert_user(user.id, user.username, user.full_name, user.language_code)
        log.info("user_start", telegram_id=user.id)
    await update.message.reply_text(messages.WELCOME, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(messages.HELP, parse_mode=ParseMode.MARKDOWN)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return
    q = parse(text)
    if q.intent != "search_cheapest" or not (q.origin and q.destination and q.departure_date):
        await update.message.reply_text(messages.PARSE_HINT, parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text(messages.format_parsed(q), parse_mode=ParseMode.MARKDOWN)

    try:
        offers = await _service(context).search(
            origin=q.origin,
            destination=q.destination,
            departure_date=q.departure_date.isoformat(),
            passengers=q.passengers,
            return_date=q.return_date.isoformat() if q.return_date else None,
        )
    except AllProvidersFailed:
        await update.message.reply_text(messages.PROVIDER_FAIL)
        return
    except Exception as e:
        log.exception("search_failed", error=str(e))
        await update.message.reply_text(messages.PROVIDER_FAIL)
        return

    await update.message.reply_text(
        messages.format_offers(offers),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )

from __future__ import annotations

import re
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.alerts.service import AlertLimitReached, AlertService
from app.bot import messages
from app.bot.middleware.rate_limit import TokenBucketRateLimiter
from app.db.database import upsert_user
from app.deals.history import route_price_history
from app.deals.scoring import recent_great_deals
from app.flights.providers.base import AllProvidersFailed
from app.flights.service import FlightService
from app.nlp.airport_aliases import find_airports
from app.nlp.parser import parse
from app.utils.logging import get_logger

log = get_logger(__name__)
MAX_INPUT_CHARS = 500


def _service(context: ContextTypes.DEFAULT_TYPE) -> FlightService:
    return context.application.bot_data["flight_service"]


def _alert_service(context: ContextTypes.DEFAULT_TYPE) -> AlertService:
    return context.application.bot_data["alert_service"]


def _rate_limiter(context: ContextTypes.DEFAULT_TYPE) -> TokenBucketRateLimiter:
    return context.application.bot_data["rate_limiter"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    user = update.effective_user
    if user:
        await upsert_user(user.id, user.username, user.full_name, user.language_code)
        log.info("user_start", telegram_id=user.id)
    await update.message.reply_text(messages.WELCOME, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    await update.message.reply_text(messages.HELP, parse_mode=ParseMode.MARKDOWN)


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    user = update.effective_user
    text = _command_payload(update)
    if not user or not text:
        await update.message.reply_text(messages.WATCH_HINT, parse_mode=ParseMode.MARKDOWN)
        return
    if _input_too_long(text):
        await update.message.reply_text(messages.INPUT_TOO_LONG)
        return

    await upsert_user(user.id, user.username, user.full_name, user.language_code)
    q = parse(text)
    if not (
        q.origin
        and q.destination
        and q.departure_date
        and q.max_price_per_person is not None
    ):
        await update.message.reply_text(messages.WATCH_HINT, parse_mode=ParseMode.MARKDOWN)
        return
    if q.max_price_per_person < 100_000 or q.max_price_per_person > 50_000_000:
        await update.message.reply_text(messages.ALERT_PRICE_INVALID)
        return

    try:
        alert = await _alert_service(context).create_or_update_alert(
            telegram_id=user.id,
            origin=q.origin,
            destination=q.destination,
            departure_date=q.departure_date.isoformat(),
            return_date=q.return_date.isoformat() if q.return_date else None,
            passengers=q.passengers,
            max_price_per_person=q.max_price_per_person,
        )
    except AlertLimitReached:
        await update.message.reply_text(messages.ALERT_LIMIT)
        return

    await update.message.reply_text(messages.format_watch_confirm(alert), parse_mode=ParseMode.MARKDOWN)


async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    user = update.effective_user
    if not user:
        return
    alerts = await _alert_service(context).list_alerts(user.id)
    keyboard = [
        [
            InlineKeyboardButton("Pause", callback_data=f"pause:{alert.id}:1d"),
            InlineKeyboardButton("Delete", callback_data=f"delete:{alert.id}"),
        ]
        for alert in alerts[:20]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(
        messages.format_alerts(alerts),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    user = update.effective_user
    deals = await recent_great_deals(user.id if user else None)
    await update.message.reply_text(
        messages.format_deals(deals),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    text = _command_payload(update)
    if not text:
        await update.message.reply_text(messages.HISTORY_HINT, parse_mode=ParseMode.MARKDOWN)
        return
    if _input_too_long(text):
        await update.message.reply_text(messages.INPUT_TOO_LONG)
        return
    route = _parse_route(text)
    if route is None:
        await update.message.reply_text(messages.HISTORY_HINT, parse_mode=ParseMode.MARKDOWN)
        return
    history = await route_price_history(route[0], route[1])
    await update.message.reply_text(messages.format_history(history), parse_mode=ParseMode.MARKDOWN)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    user = update.effective_user
    if not user or len(context.args) < 2:
        await update.message.reply_text("Dùng: `/pause <id> <1h|1d|7d>`", parse_mode=ParseMode.MARKDOWN)
        return
    alert_id = _parse_int(context.args[0])
    duration = parse_duration(context.args[1])
    if alert_id is None or duration is None:
        await update.message.reply_text("Dùng: `/pause <id> <1h|1d|7d>`", parse_mode=ParseMode.MARKDOWN)
        return
    ok = await _alert_service(context).pause_alert(user.id, alert_id, duration)
    await update.message.reply_text("⏸️ Đã tạm dừng alert." if ok else messages.ALERT_NOT_FOUND)


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    user = update.effective_user
    if not user or not context.args:
        await update.message.reply_text("Dùng: `/delete <id>`", parse_mode=ParseMode.MARKDOWN)
        return
    alert_id = _parse_int(context.args[0])
    if alert_id is None:
        await update.message.reply_text("Dùng: `/delete <id>`", parse_mode=ParseMode.MARKDOWN)
        return
    ok = await _alert_service(context).delete_alert(user.id, alert_id)
    await update.message.reply_text("🗑️ Đã xoá alert." if ok else messages.ALERT_NOT_FOUND)


async def on_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    query = update.callback_query
    user = update.effective_user
    if not query or not user or not query.data:
        return
    parts = query.data.split(":")
    action = parts[0]
    alert_id = _parse_int(parts[1]) if len(parts) >= 2 else None
    if alert_id is None:
        await query.answer("Alert không hợp lệ")
        return
    if action == "pause":
        duration = parse_duration(parts[2] if len(parts) >= 3 else "1d")
        ok = duration is not None and await _alert_service(context).pause_alert(
            user.id,
            alert_id,
            duration,
        )
        await query.answer("Đã tạm dừng" if ok else "Alert không tồn tại")
        return
    if action == "delete":
        ok = await _alert_service(context).delete_alert(user.id, alert_id)
        await query.answer("Đã xoá" if ok else "Alert không tồn tại")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_access(update, context):
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    if _input_too_long(text):
        await update.message.reply_text(messages.INPUT_TOO_LONG)
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


def parse_duration(value: str) -> timedelta | None:
    match = re.fullmatch(r"(\d+)([hd])", value.strip().lower())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        return None
    if unit == "h":
        return timedelta(hours=amount)
    return timedelta(days=amount)


def _command_payload(update: Update) -> str:
    text = (update.message.text or "").strip()
    return re.sub(r"^/\w+(?:@\w+)?\s*", "", text, count=1).strip()


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _parse_route(text: str) -> tuple[str, str] | None:
    airports = find_airports(text)
    if len(airports) < 2:
        return None
    return (airports[0][2], airports[1][2])


def _input_too_long(text: str) -> bool:
    return len(text) > MAX_INPUT_CHARS


def _owner_allowed(user_id: int | None, owner_chat_id: int | None) -> bool:
    return owner_chat_id is None or user_id == owner_chat_id


async def _check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    owner_chat_id = context.application.bot_data.get("owner_chat_id")
    if not _owner_allowed(user.id if user else None, owner_chat_id):
        if update.callback_query:
            await update.callback_query.answer(messages.OWNER_ONLY, show_alert=False)
        elif update.message:
            await update.message.reply_text(messages.OWNER_ONLY)
        return False
    return await _check_rate_limit(update, context)


async def _check_rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user is None:
        return True
    if _rate_limiter(context).allow(user.id):
        return True
    if update.callback_query:
        await update.callback_query.answer(messages.RATE_LIMITED, show_alert=False)
        return False
    if update.message:
        await update.message.reply_text(messages.RATE_LIMITED)
    return False

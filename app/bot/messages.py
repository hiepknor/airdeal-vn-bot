from __future__ import annotations

from urllib.parse import urlparse

from app.alerts.models import Alert
from app.deals.history import RoutePriceHistory, sparkline
from app.deals.scoring import ScoredOffer
from app.flights.models import FlightOffer
from app.nlp.parser import ParsedQuery
from app.utils.affiliate import safe_booking_url

WELCOME = (
    "✈️ Chào! Mình là AirDeal VN Bot, săn vé nội địa giá rẻ.\n\n"
    "Cứ gõ tự nhiên, ví dụ:\n"
    "• `hà nội đi sài gòn 20/5 2 người`\n"
    "• `mai bay đà nẵng`\n"
    "• `hn đn đi 25/6 về 28/6 2vc 1 bé`\n\n"
    "Lệnh: /search /watch /alerts /help"
)

HELP = (
    "*AirDeal VN Bot — trợ giúp*\n\n"
    "Gõ tự nhiên, hoặc dùng lệnh:\n"
    "/search — tìm vé\n"
    "/watch — tạo cảnh báo giá\n"
    "/alerts — danh sách cảnh báo\n"
    "/deals — top deal hôm nay\n"
    "/history — lịch sử giá\n"
    "/help — trợ giúp"
)

PARSE_HINT = (
    "Mình chưa hiểu rõ. Hãy thử format:\n"
    "`<điểm đi> đi <điểm đến> <ngày> <số người>`\n\n"
    "Ví dụ: `hà nội đi sài gòn 20/5 2 người`"
)

NO_RESULTS = "Không tìm thấy chuyến phù hợp. Thử ngày/route khác giúp mình."

PROVIDER_FAIL = "Hệ thống đang quá tải. Thử lại sau ít phút."

RATE_LIMITED = "Bạn thao tác hơi nhanh. Chờ một chút rồi thử lại nhé."

OWNER_ONLY = "Bot đang ở chế độ riêng tư. Tài khoản này không được phép sử dụng."

INPUT_TOO_LONG = "Tin nhắn quá dài. Vui lòng nhập tối đa 500 ký tự."

WATCH_HINT = (
    "Dùng: `/watch <điểm đi> đi <điểm đến> <ngày> dưới <giá>`\n"
    "Ví dụ: `/watch hà nội đi sài gòn 20/5 dưới 1.2tr`"
)

ALERT_NOT_FOUND = "Alert không tồn tại hoặc không thuộc tài khoản của bạn."

ALERT_LIMIT = "Bạn đã đạt giới hạn 10 alert active. Xoá bớt trước khi tạo alert mới."

ALERT_PRICE_INVALID = "Giá theo dõi phải từ 100.000đ đến 50.000.000đ/người."

NO_DEALS = "Chưa đủ dữ liệu deal tốt trong 24h qua. Quay lại sau nhé."

HISTORY_HINT = (
    "Dùng: `/history <điểm đi> đi <điểm đến>`\n"
    "Ví dụ: `/history hà nội đi sài gòn`"
)

HISTORY_NOT_ENOUGH = "Chưa đủ dữ liệu lịch sử giá cho tuyến này. Cần tối thiểu 7 ngày dữ liệu."


def format_parsed(q: ParsedQuery) -> str:
    pax = q.passengers
    parts = [
        "🔎 *Tìm chuyến:*",
        f"• Tuyến: `{q.origin} → {q.destination}`",
        f"• Ngày đi: `{q.departure_date}`",
    ]
    if q.return_date:
        parts.append(f"• Ngày về: `{q.return_date}`")
    parts.append(f"• Hành khách: {pax.adults} người lớn, {pax.children} trẻ, {pax.infants} sơ sinh")
    return "\n".join(parts)


def format_offers(offers: list[FlightOffer]) -> str:
    if not offers:
        return NO_RESULTS
    medals = ["🥇", "🥈", "🥉", "•", "•"]
    lines: list[str] = []
    for i, o in enumerate(offers[:5]):
        medal = medals[i] if i < len(medals) else "•"
        time = ""
        if o.depart_time and o.arrive_time:
            time = f"  {o.depart_time} → {o.arrive_time}"
        booking_line = _booking_line(o.booking_url, indent="   ")
        lines.append(
            f"{medal} *{o.airline}* {o.flight_number or ''}{time}\n"
            f"   {_vnd(o.price_per_person)}/người · Tổng {_vnd(o.total_price)}\n"
            f"{booking_line}"
        )
    return "\n\n".join(lines)


def format_scored_offers(scored_offers: list[ScoredOffer]) -> str:
    if not scored_offers:
        return NO_RESULTS
    medals = ["🥇", "🥈", "🥉", "•", "•"]
    lines: list[str] = []
    for i, scored in enumerate(scored_offers[:5]):
        o = scored.offer
        medal = medals[i] if i < len(medals) else "•"
        time = ""
        if o.depart_time and o.arrive_time:
            time = f"  {o.depart_time} → {o.arrive_time}"
        deal_line = _deal_line(scored)
        booking_line = _booking_line(o.booking_url, indent="   ")
        lines.append(
            f"{medal} *{o.airline}* {o.flight_number or ''}{time}\n"
            f"   {_vnd(o.price_per_person)}/người · Tổng {_vnd(o.total_price)}\n"
            f"{deal_line}\n"
            f"{booking_line}"
        )
    return "\n\n".join(lines)


def format_watch_confirm(alert: Alert) -> str:
    return (
        f"✅ Đã tạo alert #{alert.id}\n"
        f"• Tuyến: `{alert.origin} → {alert.destination}`\n"
        f"• Ngày đi: `{alert.departure_date}`\n"
        f"• Giá tối đa: {_vnd(alert.max_price_per_person)}/người"
    )


def format_alerts(alerts: list[Alert]) -> str:
    if not alerts:
        return "Bạn chưa có alert active nào."
    lines = ["*Alert đang theo dõi:*"]
    for alert in alerts[:20]:
        paused = " · đang tạm dừng" if alert.paused_until else ""
        lines.append(
            f"#{alert.id} `{alert.origin} → {alert.destination}` "
            f"{alert.departure_date} · dưới {_vnd(alert.max_price_per_person)}{paused}"
        )
    return "\n".join(lines)


def format_deals(deals: list[ScoredOffer]) -> str:
    if not deals:
        return NO_DEALS
    medals = ["🥇", "🥈", "🥉", "•", "•"]
    lines = ["*Top deal 24h qua:*"]
    for index, scored in enumerate(deals[:5]):
        offer = scored.offer
        medal = medals[index] if index < len(medals) else "•"
        time = ""
        if offer.depart_time and offer.arrive_time:
            time = f" {offer.depart_time} → {offer.arrive_time}"
        savings = ""
        if scored.median_savings_pct is not None:
            savings = f" · rẻ hơn {scored.median_savings_pct:.0f}% median"
        booking_line = _booking_line(offer.booking_url, indent="   ")
        lines.append(
            f"{medal} `{offer.origin} → {offer.destination}` {offer.departure_date}\n"
            f"   *{offer.airline}* {offer.flight_number or ''}{time}\n"
            f"   {_vnd(offer.price_per_person)}/người · Deal rất tốt (P15){savings}\n"
            f"{booking_line}"
        )
    return "\n\n".join(lines)


def format_history(history: RoutePriceHistory) -> str:
    if not history.has_enough_data:
        return HISTORY_NOT_ENOUGH
    median_values = [day.median_price for day in history.days]
    min_values = [float(day.min_price) for day in history.days]
    latest = history.days[-1]
    return (
        f"*Lịch sử giá `{history.origin} → {history.destination}` — 30 ngày*\n"
        f"Median: `{sparkline(median_values)}`\n"
        f"Min:    `{sparkline(min_values)}`\n"
        f"Ngày gần nhất: {latest.day} · min {_vnd(latest.min_price)} · "
        f"median {_vnd(round(latest.median_price))}\n"
        f"Số ngày có dữ liệu: {len(history.days)}"
    )


def format_alert_offer(offer: FlightOffer) -> str:
    time = ""
    if offer.depart_time and offer.arrive_time:
        time = f" {offer.depart_time} → {offer.arrive_time}"
    booking_line = _booking_line(offer.booking_url)
    return (
        f"🔔 *Có vé hợp alert:* `{offer.origin} → {offer.destination}`\n"
        f"*{offer.airline}* {offer.flight_number or ''}{time}\n"
        f"{_vnd(offer.price_per_person)}/người · Tổng {_vnd(offer.total_price)}\n"
        f"{booking_line}"
    )


def _vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")


def _booking_line(url: str | None, indent: str = "") -> str:
    safe_url = safe_booking_url(url)
    if not safe_url:
        return f"{indent}🔗 Chưa có link đặt vé an toàn"
    host = (urlparse(safe_url).hostname or "").lower()
    label = "Mở link tìm vé" if host == "google.com" or host.endswith(".google.com") else "Đặt vé"
    return f"{indent}🔗 [{label}]({safe_url})"


def _deal_line(scored: ScoredOffer) -> str:
    if scored.baseline.insufficient:
        return f"   📊 Chưa đủ baseline ({scored.baseline.count}/10 mẫu)"
    label = "⭐ DEAL RẤT TỐT (P15)" if scored.is_great_deal else "👍 DEAL (P25)" if scored.is_deal else "📊 Giá tham khảo"
    savings = ""
    if scored.median_savings_pct is not None:
        savings = f" · rẻ hơn {scored.median_savings_pct:.0f}% median"
    return f"   {label}{savings}"

from __future__ import annotations

from app.alerts.models import Alert
from app.flights.models import FlightOffer
from app.nlp.parser import ParsedQuery

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

WATCH_HINT = (
    "Dùng: `/watch <điểm đi> đi <điểm đến> <ngày> dưới <giá>`\n"
    "Ví dụ: `/watch hà nội đi sài gòn 20/5 dưới 1.2tr`"
)

ALERT_NOT_FOUND = "Alert không tồn tại hoặc không thuộc tài khoản của bạn."

ALERT_LIMIT = "Bạn đã đạt giới hạn 10 alert active. Xoá bớt trước khi tạo alert mới."

ALERT_PRICE_INVALID = "Giá theo dõi phải từ 100.000đ đến 50.000.000đ/người."


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
        lines.append(
            f"{medal} *{o.airline}* {o.flight_number or ''}{time}\n"
            f"   {_vnd(o.price_per_person)}/người · Tổng {_vnd(o.total_price)}\n"
            f"   🔗 [Đặt vé]({o.booking_url or '#'})"
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


def format_alert_offer(offer: FlightOffer) -> str:
    time = ""
    if offer.depart_time and offer.arrive_time:
        time = f" {offer.depart_time} → {offer.arrive_time}"
    return (
        f"🔔 *Có vé hợp alert:* `{offer.origin} → {offer.destination}`\n"
        f"*{offer.airline}* {offer.flight_number or ''}{time}\n"
        f"{_vnd(offer.price_per_person)}/người · Tổng {_vnd(offer.total_price)}\n"
        f"🔗 [Đặt vé]({offer.booking_url or '#'})"
    )


def _vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")

from __future__ import annotations

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


def format_parsed(q: ParsedQuery) -> str:
    pax = q.passengers
    parts = [
        f"🔎 *Tìm chuyến:*",
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


def _vnd(n: int) -> str:
    return f"{n:,}đ".replace(",", ".")

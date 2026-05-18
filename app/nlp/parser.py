from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.flights.models import PassengerCount
from app.nlp.airport_aliases import find_airports
from app.nlp.dates_vi import parse_explicit, parse_relative


class ParsedQuery(BaseModel):
    intent: Literal["search_cheapest", "watch", "history", "unknown"] = "unknown"
    trip_type: Literal["one_way", "round_trip"] | None = None
    origin: str | None = None
    destination: str | None = None
    departure_date: date | None = None
    return_date: date | None = None
    passengers: PassengerCount = Field(default_factory=PassengerCount)
    max_price_per_person: int | None = None
    raw_text: str
    confidence: float = 0.0


_DATE_TOKEN_RE = re.compile(
    r"\d{1,2}\s*[/\-]\s*\d{1,2}(?:\s*[/\-]\s*\d{2,4})?|\d{1,2}\s+tháng\s+\d{1,2}(?:\s+\d{4})?",
    re.IGNORECASE,
)
_LABELLED_DATE_RE = re.compile(
    rf"(?:ngày|ngay)?\s*(?P<label>đi|di|bay|về|ve)\s*"
    rf"(?:ngày|ngay)?\s*(?P<date>{_DATE_TOKEN_RE.pattern})",
    re.IGNORECASE,
)

_RELATIVE_PHRASES = [
    "hôm nay", "tối nay", "ngày mai", "mai", "ngày mốt", "mốt", "ngày kia", "kia",
    "cuối tuần này", "cuối tuần sau", "cuối tuần",
    "thứ 2 tuần này", "thứ 3 tuần này", "thứ 4 tuần này", "thứ 5 tuần này",
    "thứ 6 tuần này", "thứ 7 tuần này", "chủ nhật tuần này",
    "thứ 2 tuần sau", "thứ 3 tuần sau", "thứ 4 tuần sau", "thứ 5 tuần sau",
    "thứ 6 tuần sau", "thứ 7 tuần sau", "chủ nhật tuần sau",
    "đầu tháng", "giữa tháng", "cuối tháng",
]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower().strip())


def parse(text: str, today: date | None = None) -> ParsedQuery:
    raw = text
    if len(text) > 500:
        return ParsedQuery(raw_text=raw, intent="unknown")

    t = _norm(text)
    result = ParsedQuery(raw_text=raw)

    airports = find_airports(t)
    if len(airports) >= 2:
        result.origin = airports[0][2]
        result.destination = airports[1][2]
    elif len(airports) == 1:
        result.destination = airports[0][2]

    labelled_departure, labelled_return = _extract_labelled_dates(t, today)
    dates: list[date] = []
    for m in _DATE_TOKEN_RE.finditer(t):
        d = parse_explicit(m.group(0), today)
        if d:
            dates.append(d)

    for phrase in sorted(_RELATIVE_PHRASES, key=len, reverse=True):
        if phrase in t:
            m_month = re.search(rf"{phrase}\s+(\d{{1,2}})", t)
            target = f"{phrase} {m_month.group(1)}" if (m_month and "tháng" in phrase) else phrase
            d = parse_relative(target, today)
            if d and d not in dates:
                dates.append(d)
            t = t.replace(phrase, " ", 1)

    dates = sorted(set(dates))
    if labelled_departure and labelled_return:
        result.departure_date = labelled_departure
        result.return_date = labelled_return
        result.trip_type = "round_trip"
    elif dates:
        result.departure_date = dates[0]
        if len(dates) >= 2:
            result.return_date = dates[1]
            result.trip_type = "round_trip"
        else:
            result.trip_type = "one_way"

    result.passengers = _parse_passengers(t)

    max_price = _parse_max_price(t)
    if max_price:
        result.max_price_per_person = max_price

    score = 0.0
    if result.origin:
        score += 0.3
    if result.destination:
        score += 0.3
    if result.departure_date:
        score += 0.3
    if result.passengers.total >= 1:
        score += 0.1
    result.confidence = score

    if result.origin and result.destination and result.departure_date:
        result.intent = "search_cheapest"

    return result


def _extract_labelled_dates(t: str, today: date | None) -> tuple[date | None, date | None]:
    departure_date: date | None = None
    return_date: date | None = None
    for match in _LABELLED_DATE_RE.finditer(t):
        parsed = parse_explicit(match.group("date"), today)
        if parsed is None:
            continue
        label = match.group("label")
        if label in ("về", "ve"):
            return_date = return_date or parsed
        else:
            departure_date = departure_date or parsed
    return departure_date, return_date


_PAX_RE = re.compile(r"(\d+)\s*(người|nguoi|khách|khach|vé|ve|pax|vc|vợ chồng|vo chong)")
_CHILD_RE = re.compile(r"(\d+)\s*(trẻ|tre|trẻ em|tre em|bé|be)")
_INFANT_RE = re.compile(r"(\d+)\s*(em bé|em be|sơ sinh|so sinh|infant)")


def _parse_passengers(t: str) -> PassengerCount:
    adults = 1
    children = 0
    infants = 0

    m_inf = _INFANT_RE.search(t)
    if m_inf:
        infants = int(m_inf.group(1))
        t = t.replace(m_inf.group(0), " ", 1)

    m_child = _CHILD_RE.search(t)
    if m_child:
        children = int(m_child.group(1))
        t = t.replace(m_child.group(0), " ", 1)

    m_pax = _PAX_RE.search(t)
    if m_pax:
        adults = max(1, int(m_pax.group(1)))

    try:
        return PassengerCount(adults=adults, children=children, infants=infants)
    except ValueError:
        return PassengerCount()


_MAX_PRICE_RE = re.compile(
    r"(?:dưới|duoi|tối đa|toi da|max|khoảng|khoang)\s*(\d+(?:[\.,]\d+)?)\s*(k|tr|triệu|trieu)?",
)


def _parse_max_price(t: str) -> int | None:
    m = _MAX_PRICE_RE.search(t)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").lower()
    if unit == "k":
        return int(n * 1_000)
    if unit in ("tr", "triệu", "trieu"):
        return int(n * 1_000_000)
    return int(n) if n >= 1000 else int(n * 1_000_000)

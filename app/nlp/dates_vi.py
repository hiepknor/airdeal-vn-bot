from __future__ import annotations

import re
from datetime import date, timedelta

_WEEKDAY_VI = {
    "thứ 2": 0, "thu 2": 0, "thứ hai": 0, "thu hai": 0,
    "thứ 3": 1, "thu 3": 1, "thứ ba": 1, "thu ba": 1,
    "thứ 4": 2, "thu 4": 2, "thứ tư": 2, "thu tu": 2,
    "thứ 5": 3, "thu 5": 3, "thứ năm": 3, "thu nam": 3,
    "thứ 6": 4, "thu 6": 4, "thứ sáu": 4, "thu sau": 4,
    "thứ 7": 5, "thu 7": 5, "thứ bảy": 5, "thu bay": 5,
    "chủ nhật": 6, "chu nhat": 6, "cn": 6,
}


def _today(today: date | None) -> date:
    return today or date.today()


def parse_relative(text: str, today: date | None = None) -> date | None:
    t = text.strip().lower()
    base = _today(today)

    if t in ("hôm nay", "hom nay", "nay", "tối nay", "toi nay"):
        return base
    if t in ("mai", "ngày mai", "ngay mai"):
        return base + timedelta(days=1)
    if t in ("mốt", "mot", "ngày mốt", "ngay mot"):
        return base + timedelta(days=2)
    if t in ("kia", "ngày kia", "ngay kia"):
        return base + timedelta(days=3)

    if t in ("cuối tuần này", "cuoi tuan nay", "cuối tuần", "cuoi tuan"):
        return _next_weekday(base, 6)  # CN gần nhất
    if t in ("cuối tuần sau", "cuoi tuan sau"):
        d = _next_weekday(base, 6)
        return d + timedelta(days=7)

    for key, wd in _WEEKDAY_VI.items():
        if t == f"{key} tuần này" or t == f"{key} tuan nay" or t == key:
            return _next_weekday(base, wd)
        if t == f"{key} tuần sau" or t == f"{key} tuan sau":
            return _next_weekday(base, wd) + timedelta(days=7)

    m = re.match(r"^(đầu|giữa|cuối|dau|giua|cuoi)\s+tháng\s+(\d{1,2})$", t)
    if m:
        part, mm = m.group(1), int(m.group(2))
        year = base.year if mm >= base.month else base.year + 1
        if part in ("đầu", "dau"):
            return date(year, mm, 3)
        if part in ("giữa", "giua"):
            return date(year, mm, 15)
        return date(year, mm, 27)

    return parse_explicit(t, today)


def parse_explicit(text: str, today: date | None = None) -> date | None:
    t = text.strip().lower()
    base = _today(today)

    m = re.match(r"^(\d{1,2})\s*[/\-]\s*(\d{1,2})(?:\s*[/\-]\s*(\d{2,4}))?$", t)
    if m:
        d, mm = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else base.year
        if y < 100:
            y += 2000
        return _safe_date(y, mm, d, base)

    m = re.match(r"^(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+(\d{4}))?$", t)
    if m:
        d, mm = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else base.year
        return _safe_date(y, mm, d, base)

    return None


def _safe_date(y: int, m: int, d: int, base: date) -> date | None:
    try:
        result = date(y, m, d)
    except ValueError:
        return None
    if result < base:
        try:
            result = date(y + 1, m, d)
        except ValueError:
            return None
    return result


def _next_weekday(base: date, weekday: int) -> date:
    days_ahead = (weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)

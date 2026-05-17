from datetime import timedelta

from app.bot.handlers import parse_duration


def test_parse_duration_accepts_hours_and_days():
    assert parse_duration("1h") == timedelta(hours=1)
    assert parse_duration("7d") == timedelta(days=7)


def test_parse_duration_rejects_invalid_values():
    assert parse_duration("0h") is None
    assert parse_duration("1w") is None
    assert parse_duration("abc") is None

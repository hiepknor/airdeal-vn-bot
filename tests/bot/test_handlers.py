from datetime import timedelta

from app.bot.handlers import _input_too_long, _parse_route, _user_allowed, parse_duration


def test_parse_duration_accepts_hours_and_days():
    assert parse_duration("1h") == timedelta(hours=1)
    assert parse_duration("7d") == timedelta(days=7)


def test_parse_duration_rejects_invalid_values():
    assert parse_duration("0h") is None
    assert parse_duration("1w") is None
    assert parse_duration("abc") is None


def test_input_too_long_matches_spec_limit():
    assert _input_too_long("x" * 500) is False
    assert _input_too_long("x" * 501) is True


def test_parse_route_from_vietnamese_aliases():
    assert _parse_route("hà nội đi sài gòn") == ("HAN", "SGN")
    assert _parse_route("không rõ") is None


def test_user_allowed_is_public_when_allowed_user_ids_missing():
    assert _user_allowed(123, None) is True
    assert _user_allowed(None, None) is True


def test_user_allowed_restricts_when_allowed_user_ids_is_set():
    assert _user_allowed(123, frozenset({123, 456})) is True
    assert _user_allowed(456, frozenset({123, 456})) is True
    assert _user_allowed(789, frozenset({123, 456})) is False
    assert _user_allowed(None, frozenset({123, 456})) is False

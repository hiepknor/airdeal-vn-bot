from datetime import timedelta

from app.bot.handlers import (
    _input_too_long,
    _parse_route,
    _rank_for_display,
    _user_allowed,
    parse_duration,
)
from app.flights.models import FlightOffer


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


async def test_rank_for_display_falls_back_when_baseline_fails(monkeypatch):
    async def fail_baseline(*_args, **_kwargs):
        raise RuntimeError("db locked")

    monkeypatch.setattr("app.bot.handlers.baseline", fail_baseline)
    offers = [
        FlightOffer(
            flight_key="fallback",
            origin="HAN",
            destination="SGN",
            departure_date="2026-05-20",
            airline="Vietnam Airlines",
            price_per_person=900_000,
            total_price=900_000,
            source="test",
        )
    ]

    ranked = await _rank_for_display("HAN", "SGN", "2026-05-20", offers)

    assert len(ranked) == 1
    assert ranked[0].baseline.insufficient is True
    assert ranked[0].offer.price_per_person == 900_000

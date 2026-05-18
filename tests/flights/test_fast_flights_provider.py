from app.flights.providers.fast_flights_provider import _parse_price_vnd, _parse_time


def test_parse_price_vnd_keeps_vnd_values():
    assert _parse_price_vnd("1,090,000 VND") == 1_090_000
    assert _parse_price_vnd("1.090.000đ") == 1_090_000


def test_parse_price_vnd_converts_common_foreign_currency_values():
    assert _parse_price_vnd("SGD\xa0135") == 2_700_000
    assert _parse_price_vnd("$135") == 3_510_000


def test_parse_price_vnd_rejects_ambiguous_small_values():
    assert _parse_price_vnd("135") is None


def test_parse_time_normalizes_google_flights_strings():
    assert _parse_time("5:00 PM on Thu, May 21") == "17:00"
    assert _parse_time("10:20 AM on Thu, May 21") == "10:20"
    assert _parse_time("12:05 AM") == "00:05"
    assert _parse_time("12:30 PM") == "12:30"

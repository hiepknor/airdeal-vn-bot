from datetime import date

from app.nlp.parser import parse

TODAY = date(2026, 5, 17)


def test_parse_full_one_way():
    q = parse("hà nội đi sài gòn 20/5 2 người", TODAY)
    assert q.intent == "search_cheapest"
    assert q.origin == "HAN"
    assert q.destination == "SGN"
    assert q.departure_date == date(2026, 5, 20)
    assert q.passengers.adults == 2
    assert q.trip_type == "one_way"
    assert q.confidence >= 0.9


def test_parse_round_trip():
    q = parse("hn đn đi 25/6 về 28/6 2vc 1 bé", TODAY)
    assert q.origin == "HAN"
    assert q.destination == "DAD"
    assert q.departure_date == date(2026, 6, 25)
    assert q.return_date == date(2026, 6, 28)
    assert q.trip_type == "round_trip"
    assert q.passengers.adults == 2
    assert q.passengers.children == 1


def test_parse_round_trip_when_departure_and_return_are_same_day():
    q = parse("hà nội đi đà nẵng ngày đi 25/6 ngày về 25/6 1 người", TODAY)

    assert q.origin == "HAN"
    assert q.destination == "DAD"
    assert q.departure_date == date(2026, 6, 25)
    assert q.return_date == date(2026, 6, 25)
    assert q.trip_type == "round_trip"


def test_parse_relative_date():
    q = parse("mai bay sài gòn", TODAY)
    assert q.destination == "SGN"
    assert q.departure_date == date(2026, 5, 18)


def test_parse_unknown_too_short():
    q = parse("hi", TODAY)
    assert q.intent == "unknown"


def test_parse_too_long_rejected():
    q = parse("x" * 600, TODAY)
    assert q.intent == "unknown"


def test_parse_no_dau():
    q = parse("ha noi di da nang 20/5", TODAY)
    assert q.origin == "HAN"
    assert q.destination == "DAD"
    assert q.departure_date == date(2026, 5, 20)

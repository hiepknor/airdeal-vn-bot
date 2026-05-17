from app.utils.flight_key import make_flight_key


def test_flight_key_stable():
    a = make_flight_key("VJ", "VJ123", "2026-05-20", "06:30")
    b = make_flight_key("vj", "vj 123", "2026-05-20", "06:30")
    assert a == b


def test_flight_key_differs_by_depart_time():
    a = make_flight_key("VJ", "VJ123", "2026-05-20", "06:30")
    b = make_flight_key("VJ", "VJ123", "2026-05-20", "18:30")
    assert a != b


def test_flight_key_differs_by_date():
    a = make_flight_key("VJ", "VJ123", "2026-05-20", "06:30")
    b = make_flight_key("VJ", "VJ123", "2026-05-21", "06:30")
    assert a != b

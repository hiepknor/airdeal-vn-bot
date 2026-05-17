from datetime import date

from app.nlp.dates_vi import parse_explicit, parse_relative


TODAY = date(2026, 5, 17)  # Chủ Nhật


def test_mai():
    assert parse_relative("mai", TODAY) == date(2026, 5, 18)


def test_mot():
    assert parse_relative("mốt", TODAY) == date(2026, 5, 19)


def test_cuoi_tuan_nay():
    # Hôm nay đã là CN, "cuối tuần này" lấy CN tuần sau
    assert parse_relative("cuối tuần này", TODAY) == date(2026, 5, 24)


def test_thu_2_tuan_sau():
    # Thứ 2 gần nhất là 2026-05-18, "tuần sau" là 2026-05-25
    assert parse_relative("thứ 2 tuần sau", TODAY) == date(2026, 5, 25)


def test_dau_thang_6():
    assert parse_relative("đầu tháng 6", TODAY) == date(2026, 6, 3)


def test_explicit_dd_mm():
    assert parse_explicit("20/5", TODAY) == date(2026, 5, 20)


def test_explicit_dd_mm_yyyy():
    assert parse_explicit("20-5-2026", TODAY) == date(2026, 5, 20)


def test_explicit_past_rolls_to_next_year():
    # 1/1 đã qua → next year
    assert parse_explicit("1/1", TODAY) == date(2027, 1, 1)

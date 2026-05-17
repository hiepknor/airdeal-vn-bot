from app.utils.affiliate import inject_affiliate


def test_inject_affiliate_adds_ref():
    url = inject_affiliate("https://atadi.vn/booking/VJ123", "atadi", "airdeal")
    assert url and "ref=airdeal" in url


def test_inject_affiliate_no_id_returns_original():
    url = "https://example.com/book"
    assert inject_affiliate(url, "atadi", None) == url


def test_inject_affiliate_none_url():
    assert inject_affiliate(None, "atadi", "ref123") is None


def test_inject_affiliate_traveloka():
    url = inject_affiliate("https://traveloka.com/flight?dep=HAN", "traveloka", "myref")
    assert url and "aff_ref=myref" in url

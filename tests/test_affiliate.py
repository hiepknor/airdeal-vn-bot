from app.utils.affiliate import inject_affiliate, safe_booking_url


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


def test_safe_booking_url_allows_https_whitelisted_domains():
    assert safe_booking_url("https://atadi.vn/booking/VJ123") == "https://atadi.vn/booking/VJ123"
    assert safe_booking_url("https://www.traveloka.com/flight") == "https://www.traveloka.com/flight"


def test_safe_booking_url_rejects_unsafe_or_unknown_urls():
    assert safe_booking_url("http://atadi.vn/booking/VJ123") is None
    assert safe_booking_url("javascript:alert(1)") is None
    assert safe_booking_url("https://evil.example/book") is None

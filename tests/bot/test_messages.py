from __future__ import annotations

from app.bot.messages import format_alert_offer, format_scored_offers
from app.deals.scoring import ScoredOffer, Stats
from app.flights.models import FlightOffer


def offer(price: int = 900_000) -> FlightOffer:
    return FlightOffer(
        flight_key="message-test",
        origin="HAN",
        destination="SGN",
        departure_date="2026-06-20",
        airline="Vietnam Airlines",
        flight_number="VN123",
        depart_time="08:00",
        arrive_time="10:00",
        price_per_person=price,
        total_price=price,
        booking_url="https://www.google.com/travel/flights?q=HAN+to+SGN",
        source="test",
    )


def test_format_scored_offers_shows_baseline_deal_context():
    scored = ScoredOffer(
        offer=offer(),
        baseline=Stats(
            insufficient=False,
            count=10,
            p15=950_000,
            p25=1_000_000,
            p50=1_500_000,
            p75=2_000_000,
            prices=(900_000, 950_000, 1_000_000, 1_100_000, 1_200_000,
                    1_500_000, 1_700_000, 1_800_000, 1_900_000, 2_000_000),
        ),
        price_pct=0,
        time_score=1,
        airline_trust=1,
        score=1,
        is_deal=True,
        is_great_deal=True,
        median_savings_pct=40,
    )

    text = format_scored_offers([scored])

    assert "DEAL RẤT TỐT (P15)" in text
    assert "rẻ hơn 40% median" in text
    assert "Mở link tìm vé" in text


def test_format_scored_offers_shows_insufficient_baseline_count():
    scored = ScoredOffer(
        offer=offer(),
        baseline=Stats(insufficient=True, count=3, prices=(900_000, 950_000, 1_000_000)),
        price_pct=None,
        time_score=1,
        airline_trust=1,
        score=0,
        is_deal=False,
        is_great_deal=False,
        median_savings_pct=None,
    )

    text = format_scored_offers([scored])

    assert "Chưa đủ baseline (3/10 mẫu)" in text


def test_google_flights_links_are_not_labeled_as_direct_booking():
    text = format_alert_offer(offer())

    assert "Mở link tìm vé" in text
    assert "Đặt vé" not in text


def test_atadi_search_links_are_not_labeled_as_direct_booking():
    atadi_offer = offer()
    atadi_offer.booking_url = "https://atadi.vn/tim-ve-may-bay?ap=HAN.SGN&dt=20260521&ps=1.0.0&leg=0"

    text = format_alert_offer(atadi_offer)

    assert "Mở link tìm vé" in text
    assert "Đặt vé" not in text

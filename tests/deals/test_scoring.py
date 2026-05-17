from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.database import connect, init_db
from app.deals.scoring import Stats, baseline, percentile, percentile_rank, rank_offers, score_offer
from app.flights.models import FlightOffer


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "deals.db"
    monkeypatch.setattr("app.config.settings.database_url", f"sqlite+aiosqlite:///{db_path}")


def offer(price: int, depart_time: str = "08:00", airline: str = "VN") -> FlightOffer:
    return FlightOffer(
        flight_key=f"{airline}-{price}-{depart_time}",
        origin="HAN",
        destination="SGN",
        departure_date="2026-06-20",
        airline=airline,
        flight_number="VN123",
        depart_time=depart_time,
        arrive_time="10:00",
        price_per_person=price,
        total_price=price,
        booking_url="https://example.com",
        source="test",
    )


def test_percentile_uses_linear_interpolation():
    prices = [100, 200, 300, 400]

    assert percentile(prices, 25) == 175
    assert percentile(prices, 50) == 250
    assert percentile(prices, 75) == 325


def test_percentile_rank_bounds_prices():
    prices = [100, 200, 300, 400]

    assert percentile_rank(prices, 50) == 0
    assert percentile_rank(prices, 400) == 100
    assert percentile_rank(prices, 250) == 50


def test_score_offer_marks_deal_and_great_deal_with_baseline():
    stats = Stats(
        insufficient=False,
        count=10,
        p15=150,
        p25=250,
        p50=500,
        p75=750,
        prices=(100, 150, 200, 250, 300, 500, 700, 800, 900, 1000),
    )

    scored = score_offer(offer(140), stats)

    assert scored.is_deal is True
    assert scored.is_great_deal is True
    assert scored.median_savings_pct == pytest.approx(72)
    assert scored.score > 0


def test_rank_offers_falls_back_to_price_when_baseline_insufficient():
    stats = Stats(insufficient=True, count=2, prices=(700, 800))

    ranked = rank_offers([offer(900, "07:00"), offer(700, "23:00")], stats)

    assert [item.offer.price_per_person for item in ranked] == [700, 900]
    assert all(item.is_deal is False for item in ranked)
    assert all(item.is_great_deal is False for item in ranked)


async def test_baseline_queries_route_date_window_and_recent_snapshots(isolated_db):
    await init_db()
    created = datetime.now() - timedelta(days=1)
    prices = [100_000 * i for i in range(1, 11)]
    async with connect() as db:
        for index, price in enumerate(prices):
            await db.execute(
                "INSERT INTO price_snapshots("
                "flight_key, origin, destination, departure_date, price_per_person, source, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"fk-{index}",
                    "HAN",
                    "SGN",
                    "2026-06-20",
                    price,
                    "test",
                    created.isoformat(),
                ),
            )
        await db.execute(
            "INSERT INTO price_snapshots("
            "flight_key, origin, destination, departure_date, price_per_person, source, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old", "HAN", "SGN", "2026-06-20", 1, "test", (datetime.now() - timedelta(days=40)).isoformat()),
        )
        await db.execute(
            "INSERT INTO price_snapshots("
            "flight_key, origin, destination, departure_date, price_per_person, source, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("wrong-route", "DAD", "SGN", "2026-06-20", 1, "test", created.isoformat()),
        )
        await db.commit()

    stats = await baseline("HAN", "SGN", "2026-06-20")

    assert stats.insufficient is False
    assert stats.count == 10
    assert stats.p50 == pytest.approx(550_000)

from __future__ import annotations

from datetime import UTC, datetime

from app.db.database import connect, init_db
from app.deals.snapshots import record_price_snapshots
from app.flights.models import FlightOffer


def offer(price: int = 900_000) -> FlightOffer:
    return FlightOffer(
        flight_key="snapshot-test",
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


async def test_record_price_snapshots_inserts_search_results(tmp_path, monkeypatch):
    db_path = tmp_path / "snapshots.db"
    monkeypatch.setattr("app.config.settings.database_url", f"sqlite+aiosqlite:///{db_path}")
    await init_db()

    created_at = datetime(2026, 6, 1, tzinfo=UTC)
    count = await record_price_snapshots([offer()], created_at)

    async with connect() as db:
        cur = await db.execute("SELECT * FROM price_snapshots")
        row = await cur.fetchone()

    assert count == 1
    assert row["origin"] == "HAN"
    assert row["destination"] == "SGN"
    assert row["days_to_departure"] == 19

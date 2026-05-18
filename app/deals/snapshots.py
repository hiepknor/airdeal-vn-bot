from __future__ import annotations

from datetime import UTC, datetime

from app.db.database import connect
from app.flights.models import FlightOffer

SNAPSHOT_DEDUP_MINUTES = 30


async def record_price_snapshots(
    offers: list[FlightOffer],
    created_at: datetime | None = None,
) -> int:
    if not offers:
        return 0
    created = created_at or datetime.now(UTC)
    rows = [_snapshot_row(offer, created) for offer in offers]
    cutoff = created.timestamp() - SNAPSHOT_DEDUP_MINUTES * 60
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=UTC).isoformat()
    inserted = 0
    async with connect() as db:
        for row in rows:
            cur = await db.execute(
                "INSERT INTO price_snapshots("
                "flight_key, origin, destination, departure_date, airline, flight_number, "
                "depart_time, arrive_time, price_per_person, total_price, currency, "
                "booking_url, source, days_to_departure, created_at"
                ") "
                "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM price_snapshots "
                "  WHERE flight_key = ? AND source = ? AND price_per_person = ? "
                "  AND created_at >= ?"
                ")",
                (
                    *row,
                    row[0],
                    row[12],
                    row[8],
                    cutoff_iso,
                ),
            )
            inserted += cur.rowcount
        await db.commit()
    return inserted


def _snapshot_row(offer: FlightOffer, created: datetime) -> tuple[object, ...]:
    days_to_departure = (
        datetime.fromisoformat(offer.departure_date).date() - created.date()
    ).days
    return (
        offer.flight_key,
        offer.origin,
        offer.destination,
        offer.departure_date,
        offer.airline,
        offer.flight_number,
        offer.depart_time,
        offer.arrive_time,
        offer.price_per_person,
        offer.total_price,
        offer.currency,
        offer.booking_url,
        offer.source,
        days_to_departure,
        created.isoformat(),
    )

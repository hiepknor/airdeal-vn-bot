from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from app.config import settings
from app.db.database import connect
from app.flights.models import FlightOffer, PassengerCount
from app.utils.logging import get_logger

log = get_logger(__name__)


def make_cache_key(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    passengers: PassengerCount,
) -> str:
    raw = "|".join(
        [
            origin,
            destination,
            departure_date,
            return_date or "",
            str(passengers.adults),
            str(passengers.children),
            str(passengers.infants),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


class SearchCache:
    def __init__(self, ttl_minutes: int | None = None) -> None:
        self.ttl_minutes = settings.search_cache_ttl_minutes if ttl_minutes is None else ttl_minutes

    async def get(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer] | None:
        key = make_cache_key(origin, destination, departure_date, return_date, passengers)
        async with connect() as db:
            cur = await db.execute(
                "SELECT payload, expires_at FROM search_cache WHERE cache_key = ?",
                (key,),
            )
            row = await cur.fetchone()
            if row is None:
                return None

            if _parse_datetime(row["expires_at"]) <= _now():
                await db.execute("DELETE FROM search_cache WHERE cache_key = ?", (key,))
                await db.commit()
                return None

            try:
                payload = json.loads(row["payload"])
                return [FlightOffer.model_validate(item) for item in payload]
            except (json.JSONDecodeError, TypeError, ValidationError) as exc:
                log.warning("search_cache_corrupt", cache_key=key, error=str(exc))
                await db.execute("DELETE FROM search_cache WHERE cache_key = ?", (key,))
                await db.commit()
                return None

    async def set(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        offers: list[FlightOffer],
        return_date: str | None = None,
    ) -> None:
        key = make_cache_key(origin, destination, departure_date, return_date, passengers)
        now = _now()
        expires_at = now + timedelta(minutes=self.ttl_minutes)
        payload = json.dumps([offer.model_dump(mode="json") for offer in offers], ensure_ascii=False)
        async with connect() as db:
            await db.execute(
                "INSERT INTO search_cache(cache_key, payload, created_at, expires_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET "
                "  payload=excluded.payload, "
                "  created_at=excluded.created_at, "
                "  expires_at=excluded.expires_at",
                (key, payload, now.isoformat(), expires_at.isoformat()),
            )
            await db.commit()


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

import aiosqlite
import pytest

from app.config import settings
from app.db.database import init_db
from app.flights.cache import SearchCache, make_cache_key
from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import FlightProvider
from app.flights.service import FlightService


class CountingProvider(FlightProvider):
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        self.calls += 1
        return [
            FlightOffer(
                flight_key=f"{origin}-{destination}-{departure_date}-{self.calls}",
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                airline="Vietjet Air",
                flight_number="VJ123",
                depart_time="06:30",
                arrive_time="08:40",
                price_per_person=900_000 + self.calls,
                total_price=(900_000 + self.calls) * passengers.total,
                booking_url="https://example.com/book",
                source=self.name,
            )
        ]


@pytest.fixture()
async def cache_db(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")
    await init_db()
    return db_path


def test_make_cache_key_includes_route_dates_and_passengers():
    passengers = PassengerCount(adults=2, children=1, infants=0)

    one_way = make_cache_key("HAN", "SGN", "2026-05-20", None, passengers)
    round_trip = make_cache_key("HAN", "SGN", "2026-05-20", "2026-05-25", passengers)
    different_pax = make_cache_key(
        "HAN",
        "SGN",
        "2026-05-20",
        None,
        PassengerCount(adults=1, children=0, infants=0),
    )

    assert len(one_way) == 40
    assert one_way != round_trip
    assert one_way != different_pax


@pytest.mark.asyncio
async def test_service_returns_cached_offers_without_calling_provider(cache_db):
    passengers = PassengerCount(adults=2)
    provider = CountingProvider()
    service = FlightService([provider], cache=SearchCache(ttl_minutes=30))

    first = await service.search("HAN", "SGN", "2026-05-20", passengers)
    second = await service.search("HAN", "SGN", "2026-05-20", passengers)

    assert provider.calls == 1
    assert [offer.model_dump() for offer in second] == [offer.model_dump() for offer in first]


@pytest.mark.asyncio
async def test_expired_cache_misses_and_refreshes(cache_db):
    passengers = PassengerCount(adults=1)
    provider = CountingProvider()
    service = FlightService([provider], cache=SearchCache(ttl_minutes=0))

    first = await service.search("HAN", "SGN", "2026-05-20", passengers)
    second = await service.search("HAN", "SGN", "2026-05-20", passengers)

    assert provider.calls == 2
    assert second[0].price_per_person > first[0].price_per_person


@pytest.mark.asyncio
async def test_corrupt_cache_is_deleted_and_treated_as_miss(cache_db):
    passengers = PassengerCount(adults=1)
    key = make_cache_key("HAN", "SGN", "2026-05-20", None, passengers)
    async with aiosqlite.connect(cache_db) as db:
        await db.execute(
            "INSERT INTO search_cache(cache_key, payload, expires_at) "
            "VALUES (?, ?, datetime('now', '+30 minutes'))",
            (key, "not-json"),
        )
        await db.commit()

    provider = CountingProvider()
    service = FlightService([provider], cache=SearchCache(ttl_minutes=30))

    offers = await service.search("HAN", "SGN", "2026-05-20", passengers)

    async with aiosqlite.connect(cache_db) as db:
        cur = await db.execute("SELECT payload FROM search_cache WHERE cache_key = ?", (key,))
        row = await cur.fetchone()

    assert provider.calls == 1
    assert offers[0].source == "counting"
    assert row is not None
    assert row[0] != "not-json"

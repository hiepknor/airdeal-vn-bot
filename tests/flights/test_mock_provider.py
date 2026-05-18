import pytest

from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.mock import MockProvider
from app.flights.service import FlightService


@pytest.mark.asyncio
async def test_mock_returns_offers():
    p = MockProvider()
    offers = await p.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=2))
    assert len(offers) >= 3
    assert all(o.origin == "HAN" and o.destination == "SGN" for o in offers)
    assert all(o.total_price == o.price_per_person * 2 for o in offers)


@pytest.mark.asyncio
async def test_mock_is_deterministic():
    p = MockProvider()
    a = await p.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))
    b = await p.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))
    assert [o.flight_key for o in a] == [o.flight_key for o in b]


@pytest.mark.asyncio
async def test_service_sorts_by_price():
    svc = FlightService([MockProvider()])
    offers = await svc.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))
    prices = [o.price_per_person for o in offers]
    assert prices == sorted(prices)


class SlowProvider:
    name = "slow"
    timeout_seconds = 0.2

    async def search(self, *_args, **_kwargs):
        import asyncio

        await asyncio.sleep(0.05)
        return [
            FlightOffer(
                flight_key="slow",
                origin="HAN",
                destination="SGN",
                departure_date="2026-05-20",
                airline="Test Air",
                price_per_person=1_000_000,
                total_price=1_000_000,
                source=self.name,
            )
        ]


@pytest.mark.asyncio
async def test_service_uses_provider_specific_timeout():
    svc = FlightService([SlowProvider()])
    offers = await svc.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))

    assert offers[0].source == "slow"

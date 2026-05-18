import pytest

from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import AllProvidersFailed
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


@pytest.mark.asyncio
async def test_service_close_closes_providers():
    class CloseableProvider(MockProvider):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    provider = CloseableProvider()
    svc = FlightService([provider])

    await svc.close()

    assert provider.closed is True


@pytest.mark.asyncio
async def test_service_logs_provider_success_metrics(monkeypatch):
    events = []

    class Logger:
        def info(self, event, **kwargs):
            events.append((event, kwargs))

        def warning(self, event, **kwargs):
            events.append((event, kwargs))

    monkeypatch.setattr("app.flights.service.log", Logger())
    svc = FlightService([MockProvider()])

    await svc.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))

    event, fields = events[0]
    assert event == "provider_done"
    assert fields["provider"] == "mock"
    assert fields["status"] == "ok"
    assert fields["offer_count"] >= 1
    assert fields["duration_ms"] >= 0
    assert fields["origin"] == "HAN"
    assert fields["destination"] == "SGN"


@pytest.mark.asyncio
async def test_service_logs_provider_failure_metrics(monkeypatch):
    events = []

    class Logger:
        def info(self, event, **kwargs):
            events.append((event, kwargs))

        def warning(self, event, **kwargs):
            events.append((event, kwargs))

    class FailingProvider:
        name = "failing"

        async def search(self, *_args, **_kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.flights.service.log", Logger())
    svc = FlightService([FailingProvider()])

    with pytest.raises(AllProvidersFailed):
        await svc.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))

    event, fields = events[0]
    assert event == "provider_failed"
    assert fields["provider"] == "failing"
    assert fields["status"] == "error"
    assert fields["error_type"] == "RuntimeError"
    assert fields["duration_ms"] >= 0


def _offer(
    *,
    price: int,
    booking_url: str | None,
    source: str,
) -> FlightOffer:
    return FlightOffer(
        flight_key="same-flight",
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        airline="Vietnam Airlines",
        flight_number="VN123",
        depart_time="08:00",
        arrive_time="10:00",
        price_per_person=price,
        total_price=price,
        booking_url=booking_url,
        source=source,
    )


class StaticProvider:
    def __init__(self, name: str, offers: list[FlightOffer]) -> None:
        self.name = name
        self._offers = offers

    async def search(self, *_args, **_kwargs):
        return self._offers


@pytest.mark.asyncio
async def test_service_does_not_attach_more_expensive_booking_url_to_cheaper_offer():
    svc = FlightService([
        StaticProvider("fast", [_offer(
            price=900_000,
            booking_url="https://www.google.com/travel/flights?q=HAN+to+SGN",
            source="fast",
        )]),
        StaticProvider("direct", [_offer(
            price=950_000,
            booking_url="https://atadi.vn/booking/VN123",
            source="direct",
        )]),
    ])

    offers = await svc.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))

    assert offers[0].price_per_person == 900_000
    assert offers[0].booking_url == "https://www.google.com/travel/flights?q=HAN+to+SGN"


@pytest.mark.asyncio
async def test_service_prefers_direct_booking_url_when_duplicate_price_matches():
    svc = FlightService([
        StaticProvider("fast", [_offer(
            price=900_000,
            booking_url="https://www.google.com/travel/flights?q=HAN+to+SGN",
            source="fast",
        )]),
        StaticProvider("direct", [_offer(
            price=900_000,
            booking_url="https://atadi.vn/booking/VN123",
            source="direct",
        )]),
    ])

    offers = await svc.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=1))

    assert offers[0].price_per_person == 900_000
    assert offers[0].booking_url == "https://atadi.vn/booking/VN123"

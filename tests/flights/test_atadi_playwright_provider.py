from app.flights.models import PassengerCount
from app.flights.providers.atadi_playwright import (
    AtadiPlaywrightProvider,
    ProviderTimeout,
    _context_kwargs,
    _goto_search_page,
    _map_raw,
)


def test_context_kwargs_omits_storage_state_when_unset():
    assert _context_kwargs(None) == {}


def test_context_kwargs_includes_storage_state_when_set():
    assert _context_kwargs("/app/data/atadi_storage_state.json") == {
        "storage_state": "/app/data/atadi_storage_state.json"
    }


def test_atadi_playwright_provider_keeps_storage_state_path():
    provider = AtadiPlaywrightProvider(storage_state_path="/app/data/atadi_storage_state.json")

    assert provider._storage_state_path == "/app/data/atadi_storage_state.json"


def test_atadi_service_timeout_leaves_room_for_provider_timeout():
    provider = AtadiPlaywrightProvider()

    assert provider.timeout_seconds > 90


async def test_new_page_reuses_existing_context():
    class Context:
        def __init__(self) -> None:
            self.new_page_calls = 0

        async def new_page(self):
            self.new_page_calls += 1
            return object()

    provider = AtadiPlaywrightProvider()
    context = Context()
    provider._context = context

    page_one = await provider._new_page("test")
    page_two = await provider._new_page("test")

    assert page_one is not page_two
    assert context.new_page_calls == 2
    assert provider._context is context


async def test_new_page_recreates_broken_context(monkeypatch):
    class BrokenContext:
        async def new_page(self):
            raise RuntimeError("closed")

        async def close(self) -> None:
            pass

    class WorkingContext:
        async def new_page(self):
            return "page"

    contexts = [BrokenContext(), WorkingContext()]

    async def fake_new_cloak_context(storage_state_path):
        return contexts.pop(0)

    monkeypatch.setattr(
        "app.flights.providers.atadi_playwright._new_cloak_context",
        fake_new_cloak_context,
    )
    provider = AtadiPlaywrightProvider(use_cloak=True)

    assert await provider._new_page("test") == "page"
    assert isinstance(provider._context, WorkingContext)


async def test_search_timeout_resets_context(monkeypatch):
    provider = AtadiPlaywrightProvider()
    reset_called = False

    async def slow_scrape(*_args, **_kwargs):
        import asyncio

        await asyncio.sleep(0.01)
        return []

    async def fake_reset_context():
        nonlocal reset_called
        reset_called = True

    monkeypatch.setattr("app.flights.providers.atadi_playwright._SEARCH_TIMEOUT_S", 0.001)
    monkeypatch.setattr(provider, "_scrape", slow_scrape)
    monkeypatch.setattr(provider, "_reset_context", fake_reset_context)

    try:
        await provider.search("HAN", "SGN", "2026-05-21", PassengerCount(adults=1))
    except ProviderTimeout:
        pass

    assert reset_called is True


def test_map_raw_accepts_atadi_search_page_as_fallback_link():
    offer = _map_raw(
        {
            "airlineName": "Bamboo Airways",
            "flightNo": "QH283",
            "departTime": "22:00",
            "arriveTime": "00:15",
            "priceStr": "2.178.000₫ /khách",
            "bookingUrl": "https://atadi.vn/tim-ve-may-bay?ap=HAN.SGN&dt=20260521&ps=1.0.0&leg=0",
        },
        "HAN",
        "SGN",
        "2026-05-21",
        PassengerCount(adults=1),
        None,
        None,
    )

    assert offer is not None
    assert offer.airline == "Bamboo Airways"
    assert offer.flight_number == "QH283"
    assert offer.price_per_person == 2_178_000
    assert offer.booking_url.startswith("https://atadi.vn/tim-ve-may-bay?")


async def test_goto_search_page_uses_commit_readiness():
    class Page:
        def __init__(self) -> None:
            self.kwargs = None

        async def goto(self, url: str, **kwargs):
            self.kwargs = kwargs

    page = Page()

    await _goto_search_page(page, "https://atadi.vn/tim-ve-may-bay", "test")

    assert page.kwargs["wait_until"] == "commit"

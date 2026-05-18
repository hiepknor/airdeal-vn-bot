from app.flights.providers.atadi_playwright import AtadiPlaywrightProvider, _context_kwargs


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

    assert provider.timeout_seconds > 65

import pytest
import respx
import httpx

from app.flights.models import PassengerCount
from app.flights.providers.atadi import AtadiProvider
from app.flights.providers.base import ProviderError


MOCK_RESPONSE = {
    "data": [
        {
            "airline_code": "VJ",
            "airline_name": "Vietjet Air",
            "flight_number": "VJ123",
            "departure_time": "2026-05-20T06:30:00+07:00",
            "arrival_time": "2026-05-20T08:40:00+07:00",
            "price_per_person": 980000,
            "total_price": 1960000,
            "booking_url": "https://atadi.vn/booking/VJ123",
        },
        {
            "airline_code": "VN",
            "airline_name": "Vietnam Airlines",
            "flight_number": "VN217",
            "departure_time": "2026-05-20T09:15:00+07:00",
            "arrival_time": "2026-05-20T11:25:00+07:00",
            "price_per_person": 1250000,
            "total_price": 2500000,
            "booking_url": "https://atadi.vn/booking/VN217",
        },
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_atadi_search_success():
    respx.post("https://api.atadi.vn/v1/flights/search").mock(
        return_value=httpx.Response(200, json=MOCK_RESPONSE)
    )
    provider = AtadiProvider(api_key="test-key", affiliate_id="airdeal")
    offers = await provider.search("HAN", "SGN", "2026-05-20", PassengerCount(adults=2))
    await provider.close()

    assert len(offers) == 2
    assert offers[0].airline == "Vietjet Air"
    assert offers[0].price_per_person == 980000
    assert offers[0].depart_time == "06:30"
    assert offers[0].flight_number == "VJ123"
    assert offers[0].source == "atadi"
    # affiliate ref injected
    assert "ref=airdeal" in (offers[0].booking_url or "")


@pytest.mark.asyncio
@respx.mock
async def test_atadi_http_error_raises():
    respx.post("https://api.atadi.vn/v1/flights/search").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    provider = AtadiProvider(api_key="bad-key")
    with pytest.raises(ProviderError, match="HTTP 401"):
        await provider.search("HAN", "SGN", "2026-05-20", PassengerCount())
    await provider.close()


@pytest.mark.asyncio
@respx.mock
async def test_atadi_empty_data_returns_empty_list():
    respx.post("https://api.atadi.vn/v1/flights/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    provider = AtadiProvider(api_key="test-key")
    offers = await provider.search("HAN", "SGN", "2026-05-20", PassengerCount())
    await provider.close()
    assert offers == []

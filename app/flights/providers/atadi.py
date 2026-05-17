"""
Atadi.vn flight provider — chính thức có public API.

Để lấy API key:
1. Đăng ký tài khoản tại atadi.vn
2. Lấy mã TKTT từ trang hồ sơ
3. Email dev@atadi.vn với mã TKTT để được cấp API key
4. Set env: ATADI_API_KEY=<key>

Endpoint và schema dưới đây dựa trên mẫu REST phổ biến của các OTA VN.
Sau khi có API key, dùng DevTools (F12 → Network) khi search trên atadi.vn
để xác nhận endpoint URL và tên field chính xác, sau đó cập nhật
_SEARCH_URL, _map_offer() cho khớp.
"""
from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import FlightProvider, ProviderError, ProviderTimeout
from app.utils.affiliate import inject_affiliate
from app.utils.flight_key import make_flight_key
from app.utils.logging import get_logger

log = get_logger(__name__)

# ── Cập nhật sau khi có API key ────────────────────────────────────────────
_BASE_URL = "https://api.atadi.vn"
_SEARCH_PATH = "/v1/flights/search"   # TODO: xác nhận path thật qua DevTools
# ──────────────────────────────────────────────────────────────────────────

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "AirDealVNBot/0.1",
}


class AtadiProvider(FlightProvider):
    name = "atadi"

    def __init__(self, api_key: str, affiliate_id: str | None = None) -> None:
        self._api_key = api_key
        self._affiliate_id = affiliate_id
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={**_HEADERS, "Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        payload = {
            "departure_airport": origin,       # TODO: xác nhận field name
            "arrival_airport": destination,
            "departure_date": departure_date,   # "YYYY-MM-DD"
            "adults": passengers.adults,
            "children": passengers.children,
            "infants": passengers.infants,
        }
        if return_date:
            payload["return_date"] = return_date

        try:
            r = await self._client.post(_SEARCH_PATH, json=payload)
        except httpx.TimeoutException as e:
            raise ProviderTimeout(f"atadi timeout: {e}") from e
        except httpx.TransportError as e:
            raise ProviderError(f"atadi network error: {e}") from e

        if r.status_code != 200:
            log.warning("atadi_http_error", status=r.status_code, body=r.text[:200])
            raise ProviderError(f"atadi HTTP {r.status_code}")

        try:
            data = r.json()
        except Exception as e:
            raise ProviderError(f"atadi invalid JSON: {e}") from e

        return self._parse(data, origin, destination, departure_date, passengers, return_date)

    def _parse(
        self,
        data: dict,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None,
    ) -> list[FlightOffer]:
        # TODO: cập nhật path key theo response thực tế (thường là data["data"] hoặc data["flights"])
        raw_flights: list[dict] = data.get("data", data.get("flights", []))
        offers: list[FlightOffer] = []

        for f in raw_flights:
            try:
                offers.append(self._map_offer(f, origin, destination, departure_date, passengers, return_date))
            except Exception as e:
                log.warning("atadi_map_error", error=str(e), raw=str(f)[:100])

        return offers

    def _map_offer(
        self,
        f: dict,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None,
    ) -> FlightOffer:
        # TODO: cập nhật tên field theo response thực tế
        airline_code: str = f.get("airline_code", f.get("airline", "??")).upper()
        airline_name: str = f.get("airline_name", airline_code)
        flight_no: str | None = f.get("flight_number") or f.get("flight_no")
        depart_time: str | None = _extract_time(f.get("departure_time") or f.get("depart_at"))
        arrive_time: str | None = _extract_time(f.get("arrival_time") or f.get("arrive_at"))

        price_pp: int = int(f.get("price_per_person") or f.get("price") or f.get("fare", 0))
        total: int = int(f.get("total_price") or price_pp * passengers.total)

        raw_url: str | None = f.get("booking_url") or f.get("deep_link")
        booking_url = inject_affiliate(raw_url, "atadi", self._affiliate_id) if raw_url else None

        return FlightOffer(
            flight_key=make_flight_key(airline_code, flight_no, departure_date, depart_time),
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            airline=airline_name,
            flight_number=flight_no,
            depart_time=depart_time,
            arrive_time=arrive_time,
            price_per_person=price_pp,
            total_price=total,
            booking_url=booking_url,
            source=self.name,
            raw=f,
        )


def _extract_time(value: str | None) -> str | None:
    if not value:
        return None
    # Hỗ trợ "2026-05-20T06:30:00+07:00" hoặc "06:30" hoặc "06:30:00"
    if "T" in value:
        value = value.split("T")[1]
    parts = value.split(":")
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return None

"""
fast-flights provider — dùng Google Flights data qua ITA Matrix protobuf.
Không cần API key. Cover đủ các sân bay nội địa VN.

Hạn chế:
- Không có flight_number (Google Flights không expose)
- Giá là chuỗi text ("1,090,000 VND"), phải parse
- current_price cho context tổng thể (low/typical/high) — dùng làm hint cho deal scoring
- Không có booking_url trực tiếp → redirect về Google Flights (không có affiliate)
"""
from __future__ import annotations

import asyncio
import re
from functools import cache
from urllib.parse import urlencode

from fast_flights import Airport, FlightData, Passengers, get_flights
from fast_flights.schema import Flight as FFLight

from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import FlightProvider, ProviderError
from app.utils.flight_key import make_flight_key
from app.utils.logging import get_logger

log = get_logger(__name__)
_FX_TO_VND = {
    "SGD": 20_000,
    "USD": 26_000,
}


@cache
def _iata_to_airport() -> dict[str, Airport]:
    return {a.value: a for a in Airport}


def _to_airport(iata: str) -> Airport:
    mapping = _iata_to_airport()
    ap = mapping.get(iata.upper())
    if ap is None:
        raise ProviderError(f"fast_flights: unknown airport {iata}")
    return ap


def _parse_price_vnd(price_str: str) -> int | None:
    normalized = price_str.upper().replace("\xa0", " ")
    digits = re.sub(r"[^\d]", "", price_str)
    if not digits:
        return None
    amount = int(digits)
    if "VND" in normalized or "₫" in price_str or "Đ" in normalized:
        return amount
    for currency, rate in _FX_TO_VND.items():
        if currency in normalized or (currency == "USD" and "$" in price_str):
            return amount * rate
    return amount if amount >= 100_000 else None


def _parse_time(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", value, flags=re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = (match.group(3) or "").upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


class FastFlightsProvider(FlightProvider):
    name = "fast_flights"

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        try:
            return await asyncio.to_thread(
                self._search_sync, origin, destination, departure_date, passengers, return_date
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"fast_flights error: {e}") from e

    def _search_sync(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None,
    ) -> list[FlightOffer]:
        origin_ap = _to_airport(origin)
        dest_ap = _to_airport(destination)

        flight_data = [FlightData(date=departure_date, from_airport=origin_ap, to_airport=dest_ap)]
        trip: str = "one-way"

        if return_date:
            flight_data.append(FlightData(date=return_date, from_airport=dest_ap, to_airport=origin_ap))
            trip = "round-trip"

        pax = Passengers(
            adults=passengers.adults,
            children=passengers.children,
            infants_in_seat=passengers.infants,
        )

        result = get_flights(
            flight_data=flight_data,
            trip=trip,
            passengers=pax,
            seat="economy",
            fetch_mode="common",
        )

        offers: list[FlightOffer] = []
        for flight in result.flights:
            offer = self._map_offer(flight, origin, destination, departure_date, passengers, return_date)
            if offer:
                offers.append(offer)

        log.info(
            "fast_flights_search_done",
            origin=origin,
            destination=destination,
            date=departure_date,
            count=len(offers),
            market_price=result.current_price,
        )
        return offers

    def _map_offer(
        self,
        f: FFLight,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None,
    ) -> FlightOffer | None:
        price_pp = _parse_price_vnd(f.price)
        if not price_pp or price_pp < 100_000:
            return None

        # f.name = "Vietnam Airlines · Vietjet Air" (codeshare) hoặc "Vietjet Air"
        airline = f.name.split("·")[0].strip()

        # fast_flights không có flight_number, dùng depart_time để diff
        depart_time = _parse_time(f.departure)
        arrive_time = _parse_time(f.arrival)

        booking_url = _google_flights_search_url(origin, destination, departure_date, passengers, return_date)

        return FlightOffer(
            flight_key=make_flight_key(airline[:2].upper(), None, departure_date, depart_time),
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            airline=airline,
            flight_number=None,
            depart_time=depart_time,
            arrive_time=arrive_time,
            price_per_person=price_pp,
            total_price=price_pp * passengers.total,
            booking_url=booking_url,
            source=self.name,
        )


def _google_flights_search_url(
    origin: str,
    destination: str,
    departure_date: str,
    passengers: PassengerCount,
    return_date: str | None,
) -> str:
    params = {
        "q": (
            f"{origin} to {destination} {departure_date} "
            f"{passengers.total} passenger{'s' if passengers.total != 1 else ''}"
        )
    }
    if return_date:
        params["q"] += f" return {return_date}"
    return f"https://www.google.com/travel/flights?{urlencode(params)}"

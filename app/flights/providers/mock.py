from __future__ import annotations

import random

from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import FlightProvider
from app.utils.flight_key import make_flight_key


class MockProvider(FlightProvider):
    name = "mock"

    _AIRLINES = [
        ("VJ", "Vietjet Air"),
        ("VN", "Vietnam Airlines"),
        ("QH", "Bamboo Airways"),
        ("BL", "Pacific Airlines"),
    ]

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        rng = random.Random(f"{origin}{destination}{departure_date}")  # noqa: S311
        offers: list[FlightOffer] = []
        for code, name in self._AIRLINES:
            flight_no = f"{code}{rng.randint(100, 999)}"
            depart_hh = rng.randint(5, 22)
            depart_mm = rng.choice([0, 15, 30, 45])
            depart_time = f"{depart_hh:02d}:{depart_mm:02d}"
            arrive_hh = (depart_hh + 2) % 24
            arrive_time = f"{arrive_hh:02d}:{depart_mm:02d}"
            price = rng.randint(800_000, 2_500_000)
            offers.append(
                FlightOffer(
                    flight_key=make_flight_key(code, flight_no, departure_date, depart_time),
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    airline=name,
                    flight_number=flight_no,
                    depart_time=depart_time,
                    arrive_time=arrive_time,
                    price_per_person=price,
                    total_price=price * passengers.total,
                    booking_url=f"https://example.com/book/{flight_no}",
                    source=self.name,
                )
            )
        return sorted(offers, key=lambda o: o.price_per_person)

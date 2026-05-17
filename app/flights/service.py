from __future__ import annotations

import asyncio

from app.flights.cache import SearchCache
from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import AllProvidersFailed, FlightProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

_PROVIDER_TIMEOUT_S = 8


class FlightService:
    def __init__(self, providers: list[FlightProvider], cache: SearchCache | None = None) -> None:
        if not providers:
            raise ValueError("at least one provider required")
        self.providers = providers
        self.cache = cache

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        if self.cache is not None:
            cached = await self.cache.get(origin, destination, departure_date, passengers, return_date)
            if cached is not None:
                return cached

        results = await asyncio.gather(
            *(
                self._call(p, origin, destination, departure_date, passengers, return_date)
                for p in self.providers
            ),
            return_exceptions=True,
        )
        merged: dict[str, FlightOffer] = {}
        any_ok = False
        for r in results:
            if isinstance(r, BaseException):
                continue
            any_ok = True
            for offer in r:
                existing = merged.get(offer.flight_key)
                if existing is None or offer.price_per_person < existing.price_per_person:
                    merged[offer.flight_key] = offer
        if not any_ok:
            raise AllProvidersFailed("all providers failed")
        offers = sorted(merged.values(), key=lambda o: o.price_per_person)
        if self.cache is not None:
            await self.cache.set(origin, destination, departure_date, passengers, offers, return_date)
        return offers

    async def _call(
        self,
        provider: FlightProvider,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None,
    ) -> list[FlightOffer]:
        try:
            return await asyncio.wait_for(
                provider.search(origin, destination, departure_date, passengers, return_date),
                timeout=_PROVIDER_TIMEOUT_S,
            )
        except Exception as e:
            log.warning("provider_failed", provider=provider.name, error=str(e))
            raise

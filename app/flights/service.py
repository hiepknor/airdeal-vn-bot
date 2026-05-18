from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from app.flights.cache import SearchCache
from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import AllProvidersFailed, FlightProvider
from app.utils.affiliate import safe_booking_url
from app.utils.logging import get_logger

log = get_logger(__name__)

_PROVIDER_TIMEOUT_S = 8


class FlightService:
    def __init__(self, providers: list[FlightProvider], cache: SearchCache | None = None) -> None:
        if not providers:
            raise ValueError("at least one provider required")
        self.providers = providers
        self.cache = cache

    async def close(self) -> None:
        for provider in self.providers:
            close = getattr(provider, "close", None)
            if close is not None:
                await close()

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
                if existing is None:
                    merged[offer.flight_key] = offer
                elif offer.price_per_person < existing.price_per_person:
                    merged[offer.flight_key] = _with_preserved_booking_url(offer, existing)
                elif offer.price_per_person == existing.price_per_person:
                    merged[offer.flight_key] = _prefer_direct_booking_url(existing, offer)
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
            timeout = getattr(provider, "timeout_seconds", _PROVIDER_TIMEOUT_S)
            return await asyncio.wait_for(
                provider.search(origin, destination, departure_date, passengers, return_date),
                timeout=timeout,
            )
        except Exception as e:
            log.warning("provider_failed", provider=provider.name, error=str(e), error_type=type(e).__name__)
            raise


def _with_preserved_booking_url(selected: FlightOffer, other: FlightOffer) -> FlightOffer:
    if selected.booking_url:
        return selected
    if _is_direct_booking_url(other.booking_url) and other.price_per_person <= selected.price_per_person:
        return selected.model_copy(update={"booking_url": other.booking_url})
    return selected


def _prefer_direct_booking_url(current: FlightOffer, candidate: FlightOffer) -> FlightOffer:
    if _is_direct_booking_url(current.booking_url):
        return current
    if _is_direct_booking_url(candidate.booking_url):
        return current.model_copy(update={"booking_url": candidate.booking_url})
    return current


def _is_direct_booking_url(url: str | None) -> bool:
    safe_url = safe_booking_url(url)
    if not safe_url:
        return False
    host = (urlparse(safe_url).hostname or "").lower()
    return not (host == "google.com" or host.endswith(".google.com"))

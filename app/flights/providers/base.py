from __future__ import annotations

from abc import ABC, abstractmethod

from app.flights.models import FlightOffer, PassengerCount


class ProviderError(Exception):
    pass


class ProviderTimeout(ProviderError):
    pass


class AllProvidersFailed(ProviderError):
    pass


class FlightProvider(ABC):
    name: str

    @abstractmethod
    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        raise NotImplementedError

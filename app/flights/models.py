from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class PassengerCount(BaseModel):
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=8)
    infants: int = Field(0, ge=0, le=8)

    @model_validator(mode="after")
    def _infants_le_adults(self) -> PassengerCount:
        if self.infants > self.adults:
            raise ValueError("infants cannot exceed adults")
        if self.adults + self.children + self.infants > 9:
            raise ValueError("total passengers cannot exceed 9")
        return self

    @property
    def total(self) -> int:
        return self.adults + self.children + self.infants


class FlightOffer(BaseModel):
    flight_key: str
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    airline: str
    flight_number: str | None = None
    depart_time: str | None = None
    arrive_time: str | None = None
    price_per_person: int
    total_price: int
    currency: str = "VND"
    booking_url: str | None = None
    source: str
    cabin_class: str = "economy"
    baggage_kg: int | None = None
    raw: dict = Field(default_factory=dict)

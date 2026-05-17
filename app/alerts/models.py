from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Alert(BaseModel):
    id: int
    user_id: int
    telegram_id: int
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    trip_type: Literal["one_way", "round_trip"]
    adults: int
    children: int
    infants: int
    max_price_per_person: int
    active: bool = True
    paused_until: datetime | None = None

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import floor

from app.db.database import connect
from app.deals.scoring import percentile

HISTORY_DAYS = 30
MIN_HISTORY_DAYS = 7
SPARKLINE_LEVELS = "▁▂▃▄▅▆▇█"


@dataclass(frozen=True)
class PriceHistoryDay:
    day: str
    min_price: int
    median_price: float


@dataclass(frozen=True)
class RoutePriceHistory:
    origin: str
    destination: str
    days: list[PriceHistoryDay]

    @property
    def has_enough_data(self) -> bool:
        return len(self.days) >= MIN_HISTORY_DAYS


async def route_price_history(origin: str, destination: str) -> RoutePriceHistory:
    since = datetime.now() - timedelta(days=HISTORY_DAYS)
    async with connect() as db:
        cur = await db.execute(
            "SELECT date(created_at) AS snapshot_day, price_per_person "
            "FROM price_snapshots "
            "WHERE origin = ? AND destination = ? AND created_at >= ? "
            "ORDER BY snapshot_day ASC, price_per_person ASC",
            (origin, destination, since.isoformat()),
        )
        rows = await cur.fetchall()

    grouped: dict[str, list[int]] = {}
    for row in rows:
        grouped.setdefault(str(row["snapshot_day"]), []).append(int(row["price_per_person"]))

    days = [
        PriceHistoryDay(
            day=day,
            min_price=min(prices),
            median_price=percentile(prices, 50),
        )
        for day, prices in sorted(grouped.items())
    ]
    return RoutePriceHistory(origin=origin, destination=destination, days=days)


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    low = min(values)
    high = max(values)
    if low == high:
        return SPARKLINE_LEVELS[0] * len(values)
    scale = len(SPARKLINE_LEVELS) - 1
    return "".join(
        SPARKLINE_LEVELS[floor((value - low) / (high - low) * scale)]
        for value in values
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.db.database import connect
from app.flights.models import FlightOffer

MIN_BASELINE_SAMPLES = 10
BASELINE_WINDOW_DAYS = 7
BASELINE_LOOKBACK_DAYS = 30

AIRLINE_TRUST = {
    "VN": 1.0,
    "Vietnam Airlines": 1.0,
    "QH": 0.9,
    "Bamboo Airways": 0.9,
    "VJ": 0.85,
    "Vietjet": 0.85,
    "BL": 0.8,
    "Pacific Airlines": 0.8,
}


@dataclass(frozen=True)
class Stats:
    insufficient: bool
    count: int = 0
    p15: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    prices: tuple[int, ...] = ()


@dataclass(frozen=True)
class ScoredOffer:
    offer: FlightOffer
    baseline: Stats
    price_pct: float | None
    time_score: float
    airline_trust: float
    score: float
    is_deal: bool
    is_great_deal: bool
    median_savings_pct: float | None


async def baseline(origin: str, destination: str, departure_date: str) -> Stats:
    target_date = date.fromisoformat(departure_date)
    start_date = target_date - timedelta(days=BASELINE_WINDOW_DAYS)
    end_date = target_date + timedelta(days=BASELINE_WINDOW_DAYS)
    since = datetime.now() - timedelta(days=BASELINE_LOOKBACK_DAYS)

    async with connect() as db:
        cur = await db.execute(
            "SELECT price_per_person FROM price_snapshots "
            "WHERE origin = ? AND destination = ? "
            "AND departure_date BETWEEN ? AND ? "
            "AND created_at >= ? "
            "ORDER BY price_per_person ASC",
            (
                origin,
                destination,
                start_date.isoformat(),
                end_date.isoformat(),
                since.isoformat(),
            ),
        )
        rows = await cur.fetchall()

    prices = tuple(int(row["price_per_person"]) for row in rows)
    if len(prices) < MIN_BASELINE_SAMPLES:
        return Stats(insufficient=True, count=len(prices), prices=prices)

    return Stats(
        insufficient=False,
        count=len(prices),
        p15=percentile(prices, 15),
        p25=percentile(prices, 25),
        p50=percentile(prices, 50),
        p75=percentile(prices, 75),
        prices=prices,
    )


def percentile(values: tuple[int, ...] | list[int], percent: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * percent / 100
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * weight


def percentile_rank(values: tuple[int, ...] | list[int], price: int) -> float:
    if not values:
        raise ValueError("percentile_rank requires at least one value")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return 0.0 if price <= sorted_values[0] else 100.0
    if price <= sorted_values[0]:
        return 0.0
    if price >= sorted_values[-1]:
        return 100.0

    lower_count = sum(1 for value in sorted_values if value < price)
    equal_count = sum(1 for value in sorted_values if value == price)
    rank = lower_count + (equal_count / 2 if equal_count else 0)
    return rank / len(sorted_values) * 100


def score_offer(offer: FlightOffer, stats: Stats) -> ScoredOffer:
    time_score = _time_score(offer.depart_time)
    airline_trust = _airline_trust(offer.airline)

    if stats.insufficient:
        return ScoredOffer(
            offer=offer,
            baseline=stats,
            price_pct=None,
            time_score=time_score,
            airline_trust=airline_trust,
            score=0.0,
            is_deal=False,
            is_great_deal=False,
            median_savings_pct=None,
        )

    price_pct = percentile_rank(stats.prices, offer.price_per_person)
    score = 0.6 * (1 - price_pct / 100) + 0.25 * time_score + 0.15 * airline_trust
    median_savings_pct = None
    if stats.p50 and offer.price_per_person < stats.p50:
        median_savings_pct = (stats.p50 - offer.price_per_person) / stats.p50 * 100

    return ScoredOffer(
        offer=offer,
        baseline=stats,
        price_pct=price_pct,
        time_score=time_score,
        airline_trust=airline_trust,
        score=score,
        is_deal=stats.p25 is not None and offer.price_per_person <= stats.p25,
        is_great_deal=stats.p15 is not None and offer.price_per_person <= stats.p15,
        median_savings_pct=median_savings_pct,
    )


def rank_offers(offers: list[FlightOffer], stats: Stats) -> list[ScoredOffer]:
    scored = [score_offer(offer, stats) for offer in offers]
    if stats.insufficient:
        return sorted(scored, key=lambda item: (item.offer.price_per_person, _depart_sort(item.offer)))
    return sorted(
        scored,
        key=lambda item: (-item.score, item.offer.price_per_person, _depart_sort(item.offer)),
    )


def _time_score(depart_time: str | None) -> float:
    if depart_time is None:
        return 0.5
    try:
        parsed = time.fromisoformat(depart_time)
    except ValueError:
        return 0.5
    return 1.0 if time(6, 0) <= parsed <= time(22, 0) else 0.5


def _airline_trust(airline: str) -> float:
    return AIRLINE_TRUST.get(airline, 0.8)


def _depart_sort(offer: FlightOffer) -> str:
    return offer.depart_time or "99:99"

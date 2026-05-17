from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.alerts.models import Alert
from app.config import settings
from app.db.database import connect
from app.deals.scoring import baseline, score_offer
from app.flights.models import FlightOffer, PassengerCount
from app.utils.logging import get_logger

log = get_logger(__name__)

_RECENT_DEDUP_HOURS = 6
_ACTIVE_ALERT_LIMIT = 10


class SearchService(Protocol):
    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        ...


class AlertNotifier(Protocol):
    async def send_alert(self, telegram_id: int, offer: FlightOffer) -> None:
        ...


class AlertLimitReached(Exception):
    pass


class AlertService:
    async def create_or_update_alert(
        self,
        telegram_id: int,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None,
        passengers: PassengerCount,
        max_price_per_person: int,
    ) -> Alert:
        user_id = await self._ensure_user(telegram_id)
        trip_type = "round_trip" if return_date else "one_way"
        async with connect() as db:
            cur = await db.execute(
                "SELECT id FROM alerts "
                "WHERE user_id = ? AND origin = ? AND destination = ? "
                "AND departure_date = ? AND COALESCE(return_date, '') = ? "
                "AND max_price_per_person = ? AND active = 1 "
                "LIMIT 1",
                (
                    user_id,
                    origin,
                    destination,
                    departure_date,
                    return_date or "",
                    max_price_per_person,
                ),
            )
            existing = await cur.fetchone()
            if existing:
                await db.execute(
                    "UPDATE alerts SET trip_type = ?, adults = ?, children = ?, infants = ?, "
                    "paused_until = NULL WHERE id = ?",
                    (
                        trip_type,
                        passengers.adults,
                        passengers.children,
                        passengers.infants,
                        existing["id"],
                    ),
                )
                await db.commit()
                alert_id = int(existing["id"])
            else:
                if await self._active_alert_count(user_id) >= _ACTIVE_ALERT_LIMIT:
                    raise AlertLimitReached("active alert limit reached")
                cur = await db.execute(
                    "INSERT INTO alerts("
                    "user_id, origin, destination, departure_date, return_date, trip_type, "
                    "adults, children, infants, max_price_per_person, active"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (
                        user_id,
                        origin,
                        destination,
                        departure_date,
                        return_date,
                        trip_type,
                        passengers.adults,
                        passengers.children,
                        passengers.infants,
                        max_price_per_person,
                    ),
                )
                await db.commit()
                alert_id = int(cur.lastrowid)
        alert = await self.get_alert_by_id(alert_id)
        if alert is None:
            raise RuntimeError("created alert not found")
        return alert

    async def list_alerts(self, telegram_id: int, limit: int = 20) -> list[Alert]:
        async with connect() as db:
            cur = await db.execute(
                "SELECT a.*, u.telegram_id FROM alerts a "
                "JOIN users u ON u.id = a.user_id "
                "WHERE u.telegram_id = ? AND a.active = 1 "
                "ORDER BY a.created_at DESC LIMIT ?",
                (str(telegram_id), limit),
            )
            rows = await cur.fetchall()
        return [_alert_from_row(row) for row in rows]

    async def pause_alert(self, telegram_id: int, alert_id: int, duration: timedelta) -> bool:
        paused_until = _now() + duration
        async with connect() as db:
            cur = await db.execute(
                "UPDATE alerts SET paused_until = ? "
                "WHERE id = ? AND active = 1 "
                "AND user_id = (SELECT id FROM users WHERE telegram_id = ?)",
                (paused_until.isoformat(), alert_id, str(telegram_id)),
            )
            await db.commit()
        return cur.rowcount > 0

    async def delete_alert(self, telegram_id: int, alert_id: int) -> bool:
        async with connect() as db:
            cur = await db.execute(
                "UPDATE alerts SET active = 0 "
                "WHERE id = ? AND active = 1 "
                "AND user_id = (SELECT id FROM users WHERE telegram_id = ?)",
                (alert_id, str(telegram_id)),
            )
            await db.commit()
        return cur.rowcount > 0

    async def get_alert_by_id(self, alert_id: int) -> Alert | None:
        async with connect() as db:
            cur = await db.execute(
                "SELECT a.*, u.telegram_id FROM alerts a "
                "JOIN users u ON u.id = a.user_id "
                "WHERE a.id = ?",
                (alert_id,),
            )
            row = await cur.fetchone()
        return _alert_from_row(row) if row else None

    async def should_alert(self, alert: Alert, offer: FlightOffer) -> bool:
        if not await self._within_daily_quota(alert.user_id):
            return False

        last_sent_price = await self._recent_sent_price(alert.id, offer.flight_key)
        if last_sent_price is not None and offer.price_per_person > last_sent_price * 0.9:
            return False

        if offer.price_per_person <= alert.max_price_per_person:
            return True

        if await self._price_drop_pct(offer) >= 5:
            return True

        stats = await baseline(offer.origin, offer.destination, offer.departure_date)
        if score_offer(offer, stats).is_great_deal:
            return True

        return False

    async def scan_once(self, flight_service: SearchService, notifier: AlertNotifier) -> int:
        sent_count = 0
        for group in await self._active_groups():
            passengers = PassengerCount(
                adults=group["adults"],
                children=group["children"],
                infants=group["infants"],
            )
            try:
                offers = await flight_service.search(
                    group["origin"],
                    group["destination"],
                    group["departure_date"],
                    passengers,
                    group["return_date"],
                )
            except Exception as exc:
                log.warning("alert_scan_search_failed", route=group["route_key"], error=str(exc))
                continue

            alerts = await self._alerts_for_group(group)
            for alert in alerts:
                for offer in offers:
                    if await self.should_alert(alert, offer):
                        await notifier.send_alert(alert.telegram_id, offer)
                        await self.record_sent(alert.id, offer)
                        sent_count += 1
            for offer in offers:
                await self.record_snapshot(offer)
        return sent_count

    async def record_sent(self, alert_id: int, offer: FlightOffer) -> None:
        async with connect() as db:
            await db.execute(
                "INSERT INTO sent_notifications(alert_id, flight_key, price_per_person, sent_at) "
                "VALUES (?, ?, ?, ?)",
                (alert_id, offer.flight_key, offer.price_per_person, _now().isoformat()),
            )
            await db.commit()

    async def record_snapshot(
        self,
        offer: FlightOffer,
        created_at: datetime | None = None,
    ) -> None:
        created = created_at or _now()
        days_to_departure = (
            datetime.fromisoformat(offer.departure_date).date() - created.date()
        ).days
        async with connect() as db:
            await db.execute(
                "INSERT INTO price_snapshots("
                "flight_key, origin, destination, departure_date, airline, flight_number, "
                "depart_time, arrive_time, price_per_person, total_price, currency, "
                "booking_url, source, days_to_departure, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    offer.flight_key,
                    offer.origin,
                    offer.destination,
                    offer.departure_date,
                    offer.airline,
                    offer.flight_number,
                    offer.depart_time,
                    offer.arrive_time,
                    offer.price_per_person,
                    offer.total_price,
                    offer.currency,
                    offer.booking_url,
                    offer.source,
                    days_to_departure,
                    created.isoformat(),
                ),
            )
            await db.commit()

    async def recent_snapshots(
        self,
        origin: str,
        destination: str,
        departure_date: str,
    ) -> list[dict[str, object]]:
        async with connect() as db:
            cur = await db.execute(
                "SELECT * FROM price_snapshots "
                "WHERE origin = ? AND destination = ? AND departure_date = ? "
                "ORDER BY created_at DESC",
                (origin, destination, departure_date),
            )
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    async def _ensure_user(self, telegram_id: int) -> int:
        async with connect() as db:
            await db.execute(
                "INSERT INTO users(telegram_id) VALUES (?) "
                "ON CONFLICT(telegram_id) DO NOTHING",
                (str(telegram_id),),
            )
            cur = await db.execute("SELECT id FROM users WHERE telegram_id = ?", (str(telegram_id),))
            row = await cur.fetchone()
            await db.commit()
        if row is None:
            raise RuntimeError("user not found")
        return int(row["id"])

    async def _active_alert_count(self, user_id: int) -> int:
        async with connect() as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM alerts WHERE user_id = ? AND active = 1",
                (user_id,),
            )
            row = await cur.fetchone()
        return int(row[0])

    async def _within_daily_quota(self, user_id: int) -> bool:
        since = _now() - timedelta(days=1)
        async with connect() as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM sent_notifications sn "
                "JOIN alerts a ON a.id = sn.alert_id "
                "WHERE a.user_id = ? AND sn.sent_at >= ?",
                (user_id, since.isoformat()),
            )
            row = await cur.fetchone()
        return int(row[0]) < settings.max_alerts_per_user_per_day

    async def _recent_sent_price(self, alert_id: int, flight_key: str) -> int | None:
        since = _now() - timedelta(hours=_RECENT_DEDUP_HOURS)
        async with connect() as db:
            cur = await db.execute(
                "SELECT price_per_person FROM sent_notifications "
                "WHERE alert_id = ? AND flight_key = ? AND sent_at >= ? "
                "ORDER BY sent_at DESC LIMIT 1",
                (alert_id, flight_key, since.isoformat()),
            )
            row = await cur.fetchone()
        return int(row["price_per_person"]) if row else None

    async def _price_drop_pct(self, offer: FlightOffer) -> float:
        async with connect() as db:
            cur = await db.execute(
                "SELECT price_per_person FROM price_snapshots "
                "WHERE flight_key = ? ORDER BY created_at DESC LIMIT 1",
                (offer.flight_key,),
            )
            row = await cur.fetchone()
        if row is None:
            return 0.0
        previous = int(row["price_per_person"])
        if previous <= 0 or offer.price_per_person >= previous:
            return 0.0
        return (previous - offer.price_per_person) / previous * 100

    async def _active_groups(self) -> list[dict[str, object]]:
        now = _now().isoformat()
        async with connect() as db:
            cur = await db.execute(
                "SELECT origin, destination, departure_date, return_date, "
                "adults, children, infants, "
                "origin || '|' || destination || '|' || departure_date || '|' || "
                "COALESCE(return_date, '') || '|' || adults || '|' || children || '|' || infants "
                "AS route_key "
                "FROM alerts "
                "WHERE active = 1 AND (paused_until IS NULL OR paused_until < ?) "
                "GROUP BY origin, destination, departure_date, return_date, adults, children, infants",
                (now,),
            )
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    async def _alerts_for_group(self, group: dict[str, object]) -> list[Alert]:
        now = _now().isoformat()
        async with connect() as db:
            cur = await db.execute(
                "SELECT a.*, u.telegram_id FROM alerts a "
                "JOIN users u ON u.id = a.user_id "
                "WHERE a.active = 1 AND (a.paused_until IS NULL OR a.paused_until < ?) "
                "AND a.origin = ? AND a.destination = ? AND a.departure_date = ? "
                "AND COALESCE(a.return_date, '') = ? "
                "AND a.adults = ? AND a.children = ? AND a.infants = ?",
                (
                    now,
                    group["origin"],
                    group["destination"],
                    group["departure_date"],
                    group["return_date"] or "",
                    group["adults"],
                    group["children"],
                    group["infants"],
                ),
            )
            rows = await cur.fetchall()
        return [_alert_from_row(row) for row in rows]


def _alert_from_row(row: object) -> Alert:
    return Alert(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        telegram_id=int(row["telegram_id"]),
        origin=str(row["origin"]),
        destination=str(row["destination"]),
        departure_date=str(row["departure_date"]),
        return_date=str(row["return_date"]) if row["return_date"] else None,
        trip_type=row["trip_type"],
        adults=int(row["adults"]),
        children=int(row["children"]),
        infants=int(row["infants"]),
        max_price_per_person=int(row["max_price_per_person"]),
        active=bool(row["active"]),
        paused_until=_parse_optional_datetime(row["paused_until"]),
    )


def _parse_optional_datetime(value: object) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.alerts.service import AlertService
from app.config import settings
from app.db.database import init_db, upsert_user
from app.flights.models import FlightOffer, PassengerCount


class StaticFlightService:
    def __init__(self, offers: list[FlightOffer]) -> None:
        self.offers = offers
        self.calls = 0

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        self.calls += 1
        return self.offers


class RecordingNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[int, FlightOffer]] = []

    async def send_alert(self, telegram_id: int, offer: FlightOffer) -> None:
        self.sent.append((telegram_id, offer))


@pytest.fixture()
async def alert_service(tmp_path, monkeypatch) -> AlertService:
    db_path = tmp_path / "alerts.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(settings, "max_alerts_per_user_per_day", 10)
    await init_db()
    await upsert_user(12345, "tester", "Test User")
    return AlertService()


def _offer(price: int, flight_key: str = "vn-123") -> FlightOffer:
    return FlightOffer(
        flight_key=flight_key,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        airline="Vietnam Airlines",
        flight_number="VN123",
        depart_time="08:00",
        arrive_time="10:10",
        price_per_person=price,
        total_price=price,
        booking_url="https://example.com/book",
        source="test",
    )


@pytest.mark.asyncio
async def test_create_alert_upserts_same_condition(alert_service: AlertService):
    first = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(adults=1),
        max_price_per_person=1_000_000,
    )
    second = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(adults=2),
        max_price_per_person=1_000_000,
    )

    alerts = await alert_service.list_alerts(12345)

    assert second.id == first.id
    assert len(alerts) == 1
    assert alerts[0].adults == 2


@pytest.mark.asyncio
async def test_pause_and_delete_validate_owner(alert_service: AlertService):
    alert = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(),
        max_price_per_person=1_000_000,
    )

    assert await alert_service.pause_alert(99999, alert.id, timedelta(hours=1)) is False
    assert await alert_service.pause_alert(12345, alert.id, timedelta(hours=1)) is True
    assert await alert_service.delete_alert(99999, alert.id) is False
    assert await alert_service.delete_alert(12345, alert.id) is True
    assert await alert_service.list_alerts(12345) == []


@pytest.mark.asyncio
async def test_should_alert_respects_threshold_and_recent_dedup(alert_service: AlertService):
    alert = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(),
        max_price_per_person=1_000_000,
    )
    offer = _offer(950_000)

    assert await alert_service.should_alert(alert, offer) is True

    await alert_service.record_sent(alert.id, offer)
    assert await alert_service.should_alert(alert, _offer(920_000)) is False
    assert await alert_service.should_alert(alert, _offer(850_000)) is True


@pytest.mark.asyncio
async def test_should_alert_respects_daily_quota(alert_service: AlertService, monkeypatch):
    monkeypatch.setattr(settings, "max_alerts_per_user_per_day", 1)
    alert = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(),
        max_price_per_person=1_000_000,
    )

    await alert_service.record_sent(alert.id, _offer(950_000, "vn-1"))

    assert await alert_service.should_alert(alert, _offer(900_000, "vn-2")) is False


@pytest.mark.asyncio
async def test_scan_once_sends_and_records_snapshot(alert_service: AlertService):
    await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(),
        max_price_per_person=1_000_000,
    )
    notifier = RecordingNotifier()
    flight_service = StaticFlightService([_offer(950_000)])

    sent = await alert_service.scan_once(flight_service, notifier)

    snapshots = await alert_service.recent_snapshots("HAN", "SGN", "2026-05-20")
    assert sent == 1
    assert notifier.sent == [(12345, _offer(950_000))]
    assert flight_service.calls == 1
    assert len(snapshots) == 1


@pytest.mark.asyncio
async def test_paused_alert_is_not_scanned(alert_service: AlertService):
    alert = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(),
        max_price_per_person=1_000_000,
    )
    await alert_service.pause_alert(12345, alert.id, timedelta(days=1))
    notifier = RecordingNotifier()

    sent = await alert_service.scan_once(StaticFlightService([_offer(950_000)]), notifier)

    assert sent == 0
    assert notifier.sent == []


@pytest.mark.asyncio
async def test_price_drop_alerts_even_above_max_price(alert_service: AlertService):
    alert = await alert_service.create_or_update_alert(
        telegram_id=12345,
        origin="HAN",
        destination="SGN",
        departure_date="2026-05-20",
        return_date=None,
        passengers=PassengerCount(),
        max_price_per_person=900_000,
    )
    yesterday = datetime.now(UTC) - timedelta(days=1)
    await alert_service.record_snapshot(_offer(1_200_000), created_at=yesterday)

    assert await alert_service.should_alert(alert, _offer(1_100_000)) is True

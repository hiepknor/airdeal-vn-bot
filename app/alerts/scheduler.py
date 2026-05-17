from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.alerts.service import AlertNotifier, AlertService, SearchService
from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


class AlertScheduler:
    def __init__(
        self,
        alert_service: AlertService,
        flight_service: SearchService,
        notifier: AlertNotifier,
    ) -> None:
        self.alert_service = alert_service
        self.flight_service = flight_service
        self.notifier = notifier
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self.scheduler.add_job(
            self.run_once,
            "interval",
            minutes=settings.price_scan_interval_minutes,
            id="alert_scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        log.info("alert_scheduler_started", interval_minutes=settings.price_scan_interval_minutes)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            log.info("alert_scheduler_stopped")

    async def run_once(self) -> None:
        sent = await self.alert_service.scan_once(self.flight_service, self.notifier)
        log.info("alert_scan_completed", sent=sent)

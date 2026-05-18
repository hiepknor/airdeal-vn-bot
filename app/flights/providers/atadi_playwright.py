"""
Atadi Playwright scraper provider.

Scrape kết quả từ https://atadi.vn/tim-ve-may-bay?ap=HAN.SGN&dt=20260520&ps=1.0.0&leg=0
Không cần API key — đọc dữ liệu đã render sẵn trong DOM.

Hỗ trợ 2 backend:
  - Playwright thuần (mặc định): đơn giản, ~200MB ít hơn
  - CloakBrowser (ATADI_USE_CLOAK=true): anti-detection Chromium, tránh bị Atadi block

URL format: ap=ORIGIN.DEST, dt=YYYYMMDD[.YYYYMMDD], ps=adults.children.infants, leg=0
"""
from __future__ import annotations

import asyncio
import re

from app.flights.models import FlightOffer, PassengerCount
from app.flights.providers.base import FlightProvider, ProviderTimeout
from app.utils.affiliate import inject_affiliate
from app.utils.flight_key import make_flight_key
from app.utils.logging import get_logger

log = get_logger(__name__)

_BASE = "https://atadi.vn/tim-ve-may-bay"
_NAVIGATION_TIMEOUT_MS = 20_000
_RESULT_TIMEOUT_MS = 70_000
_SEARCH_TIMEOUT_S = 90
_SERVICE_TIMEOUT_S = _SEARCH_TIMEOUT_S + 5
_RESULT_SELECTOR = ".flightTicket__info"
_VIEWPORT = {"width": 1280, "height": 900}
_LOCALE = "vi-VN"


async def _new_playwright_context(storage_state_path: str | None = None) -> tuple[object, object, object]:
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context_kwargs = _context_kwargs(storage_state_path)
    ctx = await browser.new_context(locale=_LOCALE, viewport=_VIEWPORT, **context_kwargs)
    return pw, browser, ctx


async def _new_cloak_context(storage_state_path: str | None = None) -> object:
    import cloakbrowser

    context_kwargs = _context_kwargs(storage_state_path)
    return await cloakbrowser.launch_context_async(
        headless=True,
        locale=_LOCALE,
        viewport=_VIEWPORT,
        humanize=True,
        human_preset="default",
        stealth_args=True,
        **context_kwargs,
    )


class AtadiPlaywrightProvider(FlightProvider):
    name = "atadi_web"
    timeout_seconds = _SERVICE_TIMEOUT_S

    def __init__(
        self,
        affiliate_id: str | None = None,
        use_cloak: bool = False,
        storage_state_path: str | None = None,
    ) -> None:
        self._affiliate_id = affiliate_id
        self._use_cloak = use_cloak
        self._storage_state_path = storage_state_path
        self._context_lock = asyncio.Lock()
        self._playwright: object | None = None
        self._browser: object | None = None
        self._context: object | None = None

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        url = _build_url(origin, destination, departure_date, passengers, return_date)
        try:
            return await asyncio.wait_for(
                self._scrape(url, origin, destination, departure_date, passengers, return_date),
                timeout=_SEARCH_TIMEOUT_S,
            )
        except TimeoutError as e:
            await self._reset_context()
            raise ProviderTimeout("atadi_web timeout") from e

    async def close(self) -> None:
        async with self._context_lock:
            await self._close_context_locked()

    async def _scrape(
        self,
        url: str,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None,
    ) -> list[FlightOffer]:
        backend = "CloakBrowser" if self._use_cloak else "Playwright"
        page = await self._new_page(backend)
        try:
            await _goto_search_page(page, url, backend)
            try:
                from playwright.async_api import TimeoutError as PWTimeout
                await page.wait_for_selector(_RESULT_SELECTOR, timeout=_RESULT_TIMEOUT_MS)
            except PWTimeout:
                log.warning("atadi_web_no_results", url=url, backend=backend)
                return []

            offers = await page.evaluate(_EXTRACT_JS)
            results: list[FlightOffer] = []
            for raw in offers:
                offer = _map_raw(
                    raw, origin, destination, departure_date,
                    passengers, return_date, self._affiliate_id,
                )
                if offer:
                    results.append(offer)

            log.info(
                "atadi_web_done",
                origin=origin,
                destination=destination,
                date=departure_date,
                count=len(results),
                backend=backend,
            )
            return sorted(results, key=lambda o: o.price_per_person)
        except Exception:
            await self._reset_context()
            raise
        finally:
            await _safe_close(page)

    async def _new_page(self, backend: str) -> object:
        for attempt in range(2):
            ctx = await self._ensure_context(backend)
            try:
                return await ctx.new_page()
            except Exception as exc:
                await self._reset_context()
                if attempt == 1:
                    raise
                log.warning("atadi_web_context_recreated", backend=backend, error=str(exc))
        raise RuntimeError("unable to open Atadi page")

    async def _ensure_context(self, backend: str) -> object:
        async with self._context_lock:
            if self._context is not None:
                return self._context

            if self._use_cloak:
                self._context = await _new_cloak_context(self._storage_state_path)
            else:
                self._playwright, self._browser, self._context = await _new_playwright_context(
                    self._storage_state_path
                )
            log.info("atadi_web_context_ready", backend=backend)
            return self._context

    async def _reset_context(self) -> None:
        async with self._context_lock:
            await self._close_context_locked()

    async def _close_context_locked(self) -> None:
        context = self._context
        browser = self._browser
        playwright = self._playwright
        self._context = None
        self._browser = None
        self._playwright = None

        await _safe_close(context)
        await _safe_close(browser)
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception as exc:
                log.warning("atadi_web_playwright_stop_failed", error=str(exc))


async def _safe_close(target: object | None) -> None:
    if target is None:
        return
    try:
        await target.close()
    except Exception as exc:
        log.warning("atadi_web_close_failed", error=str(exc))


async def _goto_search_page(page: object, url: str, backend: str) -> None:
    try:
        from playwright.async_api import TimeoutError as PWTimeout
        await page.goto(url, wait_until="commit", timeout=_NAVIGATION_TIMEOUT_MS)
    except PWTimeout as exc:
        log.warning(
            "atadi_web_navigation_timeout",
            url=url,
            backend=backend,
            timeout_ms=_NAVIGATION_TIMEOUT_MS,
            error=str(exc),
        )


# JavaScript chạy trong browser để extract flight data từ DOM
_EXTRACT_JS = """
() => {
  const flights = [];
  const tickets = document.querySelectorAll('.flightTicket__info');
  tickets.forEach(ticket => {
    try {
      const card = ticket.closest('.flightTicket') || ticket.closest('.flightTicket__box') || ticket.parentElement;
      const airlineName = card?.querySelector('.flightTicket__left .text-md.font-medium, .flightTicket__left [class*="font-medium"]')?.textContent?.trim() || '';
      const flightNo = Array.from(card?.querySelectorAll('.flightTicket__left .text-sm') || [])
        .find(el => /^[A-Z0-9]{2,3}\\d{2,4}$/.test(el.textContent?.trim()))?.textContent?.trim() || null;

      const timeEls = Array.from(ticket.querySelectorAll(
        '[class*="text-base"][class*="font-semibold"], [class*="text-xl"][class*="font-semibold"]'
      ));
      const departTime = timeEls[0]?.textContent?.trim() || null;
      const arriveTime = timeEls[1]?.textContent?.trim() || null;

      const priceEl = card?.querySelector('[class*="text-primary"], [class*="price"], [class*="text-red"]')
        || Array.from(card?.querySelectorAll('*') || [])
             .find(el => el.children.length === 0 && /\\d{1,3}(\\.\\d{3})+[₫đ]/.test(el.textContent));
      const priceStr = priceEl?.textContent?.trim() || '';

      const btn = card?.querySelector('a[href]');
      const bookingUrl = btn?.href || location.href;

      if (airlineName && departTime) {
        flights.push({ airlineName, flightNo, departTime, arriveTime, priceStr, bookingUrl });
      }
    } catch(e) {}
  });
  return flights;
}
"""


def _map_raw(
    raw: dict,
    origin: str,
    destination: str,
    departure_date: str,
    passengers: PassengerCount,
    return_date: str | None,
    affiliate_id: str | None,
) -> FlightOffer | None:
    airline = raw.get("airlineName", "").strip()
    if not airline:
        return None

    digits = re.sub(r"[^\d]", "", raw.get("priceStr", ""))
    if not digits:
        return None
    price_pp = int(digits)
    if price_pp < 100_000 or price_pp > 50_000_000:
        return None

    flight_no: str | None = raw.get("flightNo")
    depart_time: str | None = (raw.get("departTime") or "")[:5] or None
    arrive_time: str | None = (raw.get("arriveTime") or "")[:5] or None

    booking_url = raw.get("bookingUrl")
    if booking_url:
        booking_url = inject_affiliate(booking_url, "atadi", affiliate_id)

    return FlightOffer(
        flight_key=make_flight_key(_airline_code(airline), flight_no, departure_date, depart_time),
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        airline=airline,
        flight_number=flight_no,
        depart_time=depart_time,
        arrive_time=arrive_time,
        price_per_person=price_pp,
        total_price=price_pp * passengers.total,
        booking_url=booking_url,
        source="atadi_web",
        raw=raw,
    )


def _build_url(
    origin: str,
    destination: str,
    departure_date: str,
    passengers: PassengerCount,
    return_date: str | None,
) -> str:
    dt = departure_date.replace("-", "")
    if return_date:
        dt += "." + return_date.replace("-", "")
    ps = f"{passengers.adults}.{passengers.children}.{passengers.infants}"
    return f"{_BASE}?ap={origin}.{destination}&dt={dt}&ps={ps}&leg=0"


def _context_kwargs(storage_state_path: str | None) -> dict[str, str]:
    if not storage_state_path:
        return {}
    return {"storage_state": storage_state_path}


_AIRLINE_CODE_MAP = {
    "vietjet": "VJ",
    "vietnam airlines": "VN",
    "bamboo": "QH",
    "pacific": "BL",
    "sunphuquoc": "9G",
    "sun air": "9G",
    "vietravel": "VU",
    "thai vietjet": "VZ",
}


def _airline_code(name: str) -> str:
    lower = name.lower()
    for key, code in _AIRLINE_CODE_MAP.items():
        if key in lower:
            return code
    return name[:2].upper()

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.database import connect, init_db
from app.deals.history import route_price_history, sparkline


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "history.db"
    monkeypatch.setattr("app.config.settings.database_url", f"sqlite+aiosqlite:///{db_path}")


def test_sparkline_scales_values():
    assert sparkline([1, 2, 3]) == "▁▄█"
    assert sparkline([5, 5, 5]) == "▁▁▁"
    assert sparkline([]) == ""


async def test_route_price_history_groups_min_and_median_by_snapshot_day(isolated_db):
    await init_db()
    now = datetime.now()
    async with connect() as db:
        for day_offset in range(7):
            day = now - timedelta(days=day_offset)
            for price in (900_000, 1_100_000, 1_300_000):
                await db.execute(
                    "INSERT INTO price_snapshots("
                    "flight_key, origin, destination, departure_date, price_per_person, source, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"fk-{day_offset}-{price}",
                        "HAN",
                        "SGN",
                        "2026-06-20",
                        price + day_offset,
                        "test",
                        day.isoformat(),
                    ),
                )
        await db.execute(
            "INSERT INTO price_snapshots("
            "flight_key, origin, destination, departure_date, price_per_person, source, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old", "HAN", "SGN", "2026-06-20", 1, "test", (now - timedelta(days=40)).isoformat()),
        )
        await db.commit()

    history = await route_price_history("HAN", "SGN")

    assert history.has_enough_data is True
    assert len(history.days) == 7
    assert history.days[-1].min_price >= 900_000
    assert history.days[-1].median_price >= 1_100_000

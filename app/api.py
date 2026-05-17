from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
from fastapi import FastAPI, Response, status

from app.config import settings
from app.db.database import connect, init_db


async def check_database() -> bool:
    try:
        async with connect() as db:
            await db.execute("SELECT 1")
    except (OSError, aiosqlite.Error):
        return False
    return True


def provider_statuses() -> dict[str, str]:
    statuses = {
        "fast_flights": "enabled" if settings.fast_flights_enabled else "disabled",
        "atadi_web": "enabled" if settings.atadi_web_enabled else "disabled",
    }
    if settings.atadi_enabled:
        statuses["atadi_rest"] = "enabled" if settings.atadi_api_key else "missing_api_key"
    else:
        statuses["atadi_rest"] = "disabled"
    return statuses


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


def create_api() -> FastAPI:
    api = FastAPI(title="AirDeal VN Bot", lifespan=lifespan)

    @api.get("/health")
    async def health(response: Response) -> dict[str, Any]:
        db_ok = await check_database()
        if not db_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "error",
            "providers": provider_statuses(),
        }

    return api


app = create_api()

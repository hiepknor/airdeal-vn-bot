from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _db_path() -> str:
    return settings.sqlite_path


async def init_db() -> None:
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.commit()
        await _apply_migrations(db)
    log.info("db_initialized", path=path)


async def _applied_versions(db: aiosqlite.Connection) -> set[str]:
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    await db.commit()
    cur = await db.execute("SELECT version FROM schema_migrations")
    rows = await cur.fetchall()
    return {r[0] for r in rows}


async def _apply_migrations(db: aiosqlite.Connection) -> None:
    applied = await _applied_versions(db)
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for f in files:
        version = f.stem
        if version in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        await db.executescript(sql)
        await db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        await db.commit()
        log.info("migration_applied", version=version)


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    db = await aiosqlite.connect(_db_path())
    try:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON;")
        yield db
    finally:
        await db.close()


async def upsert_user(
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    language_code: str | None = "vi",
) -> None:
    async with connect() as db:
        await db.execute(
            "INSERT INTO users(telegram_id, username, full_name, language_code) "
            "VALUES(?, ?, ?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET "
            "  username=excluded.username, full_name=excluded.full_name",
            (str(telegram_id), username, full_name, language_code or "vi"),
        )
        await db.commit()

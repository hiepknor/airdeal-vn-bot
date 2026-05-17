# ADR-0002: Storage evolution — SQLite WAL → PostgreSQL ở V0.5

- **Status**: Accepted
- **Date**: 2026-05-17
- **Deciders**: hiepknor

## Context

Bot có 3 nguồn ghi DB đồng thời:

1. **Bot handler** (async, mỗi message user): upsert `users`, insert `alerts`, đọc `price_snapshots`.
2. **Price scan worker** (APScheduler, mỗi 60 phút): insert hàng loạt `price_snapshots`.
3. **Alert notifier** (sau mỗi scan): insert `sent_notifications`.

SQLite mặc định **journal=DELETE** → khi worker batch insert, bot handler bị **database is locked** ngay lập tức nếu có 2+ user gõ cùng lúc.

Cần quyết định: MVP dùng gì, khi nào migrate.

## Decision

### V0.1 → V0.4: SQLite với WAL mode

- File `data/airdeal.db`.
- Bật `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL` + `PRAGMA busy_timeout=5000`.
- Dùng `aiosqlite` (async driver) — không block event loop của bot.
- Connection per-request (không pool — SQLite không lợi từ pool).
- Migration thủ công qua SQL file trong `app/db/migrations/` đánh số `0001_*.sql`, `0002_*.sql`...
- Backup: daily `sqlite3 backup` cron, giữ 7 ngày.

### V0.5: Migrate sang PostgreSQL

Trigger migrate khi đạt **1 trong các điều kiện**:

- DAU > 500.
- `price_snapshots` > 5 triệu row.
- DB file > 500 MB.
- Worker scan tốn > 5 phút/cycle do query chậm.

Migrate plan:

1. Setup Postgres parallel, dual-write trong 1 tuần (feature flag).
2. Backfill từ SQLite dump.
3. Verify count + sample diff.
4. Cutover: tắt SQLite write, đọc Postgres.
5. Giữ SQLite read-only 30 ngày làm fallback.

Sau khi migrate dùng **Alembic** cho migration thay vì SQL file thủ công.

## Consequences

### Tích cực

- MVP zero-ops, deploy 1 container, không cần DB server riêng.
- WAL mode cho phép concurrent read + 1 writer → đủ cho < 500 DAU.
- Migration thủ công đơn giản, audit-friendly cho MVP.

### Tiêu cực / Rủi ro

- SQLite không scale horizontal → V0.5 phải migrate, không thể trì hoãn.
- Backup file-level → nếu corrupt giữa flush mất data 1 giờ. Mitigation: WAL checkpoint + Litestream (V0.3+).
- Migration thủ công dễ quên order → enforce naming `NNNN_description.sql` + script kiểm tra checksum.

## Alternatives considered

| Phương án | Lý do loại |
|---|---|
| Postgres ngay từ V0.1 | Over-engineering cho MVP, tốn 1 container + ops effort, không cần thiết cho < 100 DAU |
| MongoDB | Không phù hợp dữ liệu quan hệ (alerts × users × snapshots) |
| Litestream từ V0.1 | Thêm dependency, MVP backup file đủ |

## References

- [SPEC.md §6](../../SPEC.md) — Alert worker failure modes
- SQLite WAL docs: https://www.sqlite.org/wal.html

-- AirDeal VN Bot — initial schema (V0.1)

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     TEXT UNIQUE NOT NULL,
    username        TEXT,
    full_name       TEXT,
    language_code   TEXT DEFAULT 'vi',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL,
    origin                  TEXT NOT NULL,
    destination             TEXT NOT NULL,
    departure_date          DATE NOT NULL,
    return_date             DATE,
    trip_type               TEXT NOT NULL CHECK (trip_type IN ('one_way','round_trip')),
    adults                  INTEGER DEFAULT 1,
    children                INTEGER DEFAULT 0,
    infants                 INTEGER DEFAULT 0,
    max_price_per_person    INTEGER,
    active                  BOOLEAN DEFAULT 1,
    paused_until            DATETIME,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_active_route
    ON alerts(active, origin, destination, departure_date);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_key          TEXT NOT NULL,
    origin              TEXT NOT NULL,
    destination         TEXT NOT NULL,
    departure_date      DATE NOT NULL,
    airline             TEXT,
    flight_number       TEXT,
    depart_time         TEXT,
    arrive_time         TEXT,
    price_per_person    INTEGER NOT NULL,
    total_price         INTEGER,
    currency            TEXT DEFAULT 'VND',
    booking_url         TEXT,
    source              TEXT NOT NULL,
    days_to_departure   INTEGER,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snapshots_route_date
    ON price_snapshots(origin, destination, departure_date, created_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_flight_key
    ON price_snapshots(flight_key, created_at);

CREATE TABLE IF NOT EXISTS sent_notifications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id            INTEGER NOT NULL,
    flight_key          TEXT NOT NULL,
    price_per_person    INTEGER,
    sent_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alerts(id)
);
CREATE INDEX IF NOT EXISTS idx_sent_dedup
    ON sent_notifications(alert_id, flight_key, sent_at);

CREATE TABLE IF NOT EXISTS search_cache (
    cache_key   TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL
);

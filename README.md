# ✈️ AirDeal VN Bot

Bot Telegram săn vé máy bay giá rẻ nội địa Việt Nam — **VN-first, affiliate-first, có price prediction**.

> Đọc [AGENTS.md](AGENTS.md) trước khi đóng góp code (cho cả người và AI agent).
> Spec chi tiết: [SPEC.md](SPEC.md). Quyết định kiến trúc: [docs/adr/](docs/adr/).

---

# 🎯 Mục tiêu

AirDeal VN Bot giúp người dùng:

* Tìm vé máy bay **nội địa VN** giá rẻ qua các nguồn phù hợp thị trường VN (Traveloka, Vexere, Atadi, Trip.com…).
* Gõ lệnh tự nhiên bằng **tiếng Việt** (có dấu, không dấu, viết tắt, thời gian tương đối).
* Theo dõi tuyến bay theo ngân sách + nhận alert qua Telegram.
* **Khuyến nghị "nên mua hay chờ"** dựa trên lịch sử giá (P25/P50/P75 + trend) — đây là điểm khác biệt cốt lõi.
* Booking link có affiliate ref để bot tự nuôi server (không thu phí user).

Bot **không** tự đặt vé, **không** thanh toán, **không** đăng nhập tài khoản hãng bay thay user.

---

# 🧪 Ví dụ người dùng

### One-way

```text
hà nội đi sài gòn 2 người ngày 20/5/2026 tìm rẻ nhất
```

Parse:

```json
{
  "intent": "search_cheapest",
  "trip_type": "one_way",
  "origin": "HAN",
  "destination": "SGN",
  "departure_date": "2026-05-20",
  "passengers": {"adults": 2, "children": 0, "infants": 0}
}
```

### Round-trip

```text
hn đn đi 25/6 về 28/6 2vc 1 bé
```

Parse:

```json
{
  "intent": "search_cheapest",
  "trip_type": "round_trip",
  "origin": "HAN",
  "destination": "DAD",
  "departure_date": "2026-06-25",
  "return_date": "2026-06-28",
  "passengers": {"adults": 2, "children": 0, "infants": 1}
}
```

### Flexible date

```text
rẻ nhất tháng 7 hn đi phú quốc
```

Parse → fanout 30 ngày, trả heat-map giá theo ngày.

### Time-relative

```text
mai bay sg, cuối tuần này về
```

Parse `mai` = today+1, `cuối tuần này` = Chủ Nhật gần nhất (qua `dates_vi.py`).

### Sample bot reply

```text
✅ Top deal HAN → SGN — 20/05/2026 (2 người)

🥇 Vietjet VJ123  06:30 → 08:40
   980.000đ/người · Tổng 1.960.000đ
   ⭐ DEAL (P15) — rẻ hơn 23% median 30 ngày
   🔗 Đặt: traveloka.com/?ref=airdeal

🥈 Vietnam Airlines VN217  09:15 → 11:25
   1.190.000đ/người · Tổng 2.380.000đ
   👍 Giờ đẹp · Hãng full-service
   🔗 Đặt: trip.com/?ref=airdeal

💡 Gợi ý: giá đang ở P15 — RẺ hiếm gặp, nên đặt sớm.
   Dùng /watch để theo dõi tiếp nếu chưa quyết.
```

---

# ✅ MVP Scope (V0.1)

## Có trong MVP

* Telegram bot (long polling + webhook tuỳ env).
* NLP parser tiếng Việt: regex + `dateparser` + `dates_vi.py` (mai/cuối tuần/tuần sau).
* Airport alias map (đầy đủ sân bay VN nội địa).
* Round-trip + passenger breakdown (adult/child/infant).
* **1 provider VN thật** (Traveloka affiliate hoặc Vexere/Atadi scraper) + mock provider cho test.
* Tìm vé rẻ nhất, trả top 3–5 kết quả.
* `flight_key = sha1(airline|flight_number|date|depart_time)` cho dedup.
* Alert theo tuyến + max price + WAL-mode SQLite + APScheduler worker.
* Telegram webhook `secret_token` verify + per-user rate limit (token bucket).
* Structured logging (`structlog`) + `/health` endpoint.
* Affiliate ref code injected vào booking_url.
* Docker Compose deploy.

## Chưa làm trong MVP

* Tự đặt vé, thanh toán, đăng nhập hãng bay.
* LLM parser (V0.3).
* Price prediction module đầy đủ (V0.4 — MVP chỉ ghi history).
* Postgres / Redis / Celery (V0.5).
* Web app / Zalo bot (V1.0).

---

# 🧱 Tech Stack

### MVP (V0.1)

```text
Python 3.11+
python-telegram-bot[ext] >= 21
FastAPI + uvicorn
APScheduler
httpx[http2]
aiosqlite (SQLite WAL mode)
pydantic v2 + pydantic-settings
dateparser
structlog
tenacity
beautifulsoup4 + lxml (cho scraper provider)
Playwright (fallback scraper, lazy load)
```

### Upgrade theo phase

* V0.5: PostgreSQL, Redis, Celery, Sentry, Prometheus
* V0.3+: Anthropic SDK (Claude Haiku LLM parser)
* V1.0: Next.js (web), Zalo OA SDK

---

# 🏗 Architecture

```text
Telegram User
    ↓
Telegram Bot (python-telegram-bot)
    ↓ rate-limit middleware
NLP Parser (regex → dates_vi → intent classifier → LLM fallback)
    ↓
Airport Mapper
    ↓
Flight Search Service ─── Cache (TTL 30m)
    │
    ├─ parallel fanout ──→ Provider 1 (Traveloka affiliate)
    │                       Provider 2 (Vexere scraper)
    │                       Provider 3 (Atadi scraper)
    │                       Provider N (Playwright fallback)
    ↓ merge by flight_key, keep cheapest
Deal Engine (baseline percentile + scoring + recommendation)
    ↓
Database (SQLite WAL → Postgres ở V0.5)
    ↓
Telegram Notifier ←── Alert Scheduler (APScheduler)
                       ↑
                  Price Snapshot Worker
```

---

# 📁 Project Structure

```text
airdeal-vn-bot/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── bot/
│   │   ├── telegram_bot.py
│   │   ├── handlers.py
│   │   ├── messages.py
│   │   ├── keyboards.py              # V0.3
│   │   ├── conversations/            # V0.3
│   │   └── middleware/
│   │       ├── rate_limit.py
│   │       └── webhook_auth.py
│   ├── nlp/
│   │   ├── parser.py                 # orchestrator
│   │   ├── regex_parser.py
│   │   ├── dates_vi.py               # mai/cuối tuần/tuần sau
│   │   ├── airport_aliases.py
│   │   └── llm_parser.py             # V0.3
│   ├── flights/
│   │   ├── models.py                 # pydantic v2
│   │   ├── service.py                # fanout + merge + cache
│   │   ├── cache.py
│   │   ├── flex_date_search.py       # V0.3
│   │   └── providers/
│   │       ├── base.py
│   │       ├── mock.py
│   │       ├── traveloka.py
│   │       ├── vexere.py
│   │       ├── atadi.py
│   │       └── playwright_provider.py
│   ├── deals/
│   │   ├── scoring.py                # baseline-aware
│   │   ├── history.py                # query price_snapshots
│   │   └── filters.py
│   ├── predict/                      # V0.4
│   │   ├── trend.py
│   │   └── recommender.py
│   ├── alerts/
│   │   ├── service.py
│   │   ├── scheduler.py
│   │   ├── notifier.py
│   │   └── digest.py                 # V0.4
│   ├── db/
│   │   ├── database.py               # WAL mode
│   │   ├── models.py
│   │   └── migrations/
│   └── utils/
│       ├── dates.py
│       ├── money.py
│       ├── logging.py                # structlog
│       └── flight_key.py
├── tests/
│   ├── nlp/
│   ├── flights/
│   ├── deals/
│   └── alerts/
├── docs/
│   └── adr/
│       ├── 0001-provider-strategy.md
│       ├── 0002-storage-evolution.md
│       ├── 0003-nlp-strategy.md
│       └── 0004-alert-dedup.md
├── SPEC.md
├── AGENTS.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

# 🗃 Database Schema

### users

```sql
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     TEXT UNIQUE NOT NULL,
    username        TEXT,
    full_name       TEXT,
    language_code   TEXT DEFAULT 'vi',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### alerts

```sql
CREATE TABLE alerts (
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
CREATE INDEX idx_alerts_active_route ON alerts(active, origin, destination, departure_date);
```

### price_snapshots

Mỗi lần worker quét giá, insert 1 row per offer. Dùng để build baseline + prediction.

```sql
CREATE TABLE price_snapshots (
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
    source              TEXT NOT NULL,         -- 'traveloka','vexere',...
    days_to_departure   INTEGER,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_snapshots_route_date ON price_snapshots(origin, destination, departure_date, created_at);
CREATE INDEX idx_snapshots_flight_key ON price_snapshots(flight_key, created_at);
```

### sent_notifications

```sql
CREATE TABLE sent_notifications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id            INTEGER NOT NULL,
    flight_key          TEXT NOT NULL,
    price_per_person    INTEGER,
    sent_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alerts(id)
);
CREATE INDEX idx_sent_dedup ON sent_notifications(alert_id, flight_key, sent_at);
```

### search_cache

```sql
CREATE TABLE search_cache (
    cache_key   TEXT PRIMARY KEY,        -- sha1(origin|dest|date|return|pax)
    payload     TEXT NOT NULL,           -- JSON list[FlightOffer]
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL
);
```

---

# 🧠 NLP Parser

**Quy tắc**: regex trước → `dates_vi` resolve thời gian tương đối → intent classifier → LLM fallback (V0.3, có cost cap).

Chi tiết acceptance criteria & edge case: [SPEC.md](SPEC.md) §3.
Quyết định kiến trúc: [docs/adr/0003-nlp-strategy.md](docs/adr/0003-nlp-strategy.md).

### Vietnamese date tokens (phải hiểu)

```text
mai, mốt, kia, ngày kia
hôm nay, tối nay
thứ 2/3/.../CN tuần này, tuần sau
cuối tuần này, cuối tuần sau
đầu/giữa/cuối tháng <N>
20/5, 20-5, 20/05/2026, 20 tháng 5
```

### Airport Alias (rút gọn — full trong `app/nlp/airport_aliases.py`)

```python
AIRPORT_ALIASES = {
    "hà nội": "HAN", "hn": "HAN", "nội bài": "HAN",
    "sài gòn": "SGN", "saigon": "SGN", "sg": "SGN", "tphcm": "SGN", "tsn": "SGN",
    "đà nẵng": "DAD", "danang": "DAD", "dn": "DAD",
    "nha trang": "CXR", "cam ranh": "CXR",
    "phú quốc": "PQC", "phu quoc": "PQC", "pq": "PQC",
    "đà lạt": "DLI", "da lat": "DLI", "liên khương": "DLI",
    "huế": "HUI", "hue": "HUI", "phú bài": "HUI",
    "vinh": "VII",
    "cần thơ": "VCA", "can tho": "VCA",
    "hải phòng": "HPH", "cát bi": "HPH",
    "quy nhơn": "UIH", "phù cát": "UIH",
    "buôn ma thuột": "BMV", "ban mê": "BMV",
    "thanh hoá": "THD", "thọ xuân": "THD",
    "đồng hới": "VDH", "quảng bình": "VDH",
    "chu lai": "VCL", "tam kỳ": "VCL",
    "tuy hoà": "TBB", "phú yên": "TBB",
    "pleiku": "PXU", "gia lai": "PXU",
    "côn đảo": "VCS", "côn sơn": "VCS",
    "rạch giá": "VKG"
}
```

---

# 🔎 Flight Provider Interface

```python
from pydantic import BaseModel

class PassengerCount(BaseModel):
    adults: int = 1
    children: int = 0
    infants: int = 0

class FlightOffer(BaseModel):
    flight_key: str            # sha1(airline|flight_number|date|depart_time)
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    airline: str
    flight_number: str | None = None
    depart_time: str | None = None
    arrive_time: str | None = None
    price_per_person: int
    total_price: int
    currency: str = "VND"
    booking_url: str | None = None     # đã inject affiliate ref
    source: str                         # 'traveloka','vexere',...
    cabin_class: str = "economy"
    baggage_kg: int | None = None
    raw: dict = {}                      # provider raw payload

class FlightProvider:
    name: str

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: PassengerCount,
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        raise NotImplementedError
```

Provider chain: gọi song song qua `asyncio.gather` + `tenacity` retry + timeout 8s. Merge bằng `flight_key`, giữ giá thấp nhất.

Chi tiết: [docs/adr/0001-provider-strategy.md](docs/adr/0001-provider-strategy.md).

---

# 🧮 Deal Scoring

```text
Cho mỗi route (origin, destination, departure_date ± 7d):
    history = price_snapshots last 30 days
    p25, p50, p75 = percentile(history.price_per_person)

Cho mỗi offer:
    price_pct       = percentile_rank(offer.price, history)
    time_score      = 1.0 nếu 06:00–22:00, 0.5 nếu khác
    airline_trust   = {VN: 1.0, QH: 0.9, VJ: 0.85, BL: 0.8}
    score           = 0.6*(1 - price_pct/100) + 0.25*time_score + 0.15*airline_trust

    is_deal         = price <= p25
    is_great_deal   = price <= p15
```

Bot trả:

* **Rẻ nhất**: lowest price
* **Đáng mua nhất**: highest score
* **Deal cảnh báo**: `is_great_deal`

Chi tiết: [docs/adr/0004-alert-dedup.md](docs/adr/0004-alert-dedup.md).

---

# 🔔 Alert Logic

```text
Trigger gửi alert khi:
  1. price_per_person <= alert.max_price_per_person, HOẶC
  2. price giảm >= 5% so với snapshot trước cùng flight_key, HOẶC
  3. is_great_deal == true (P15)

Dedup:
  - Cùng (alert_id, flight_key) không gửi lại trong 6 giờ
  - Trừ khi giá giảm thêm >= 10% so với lần gửi trước

Giới hạn:
  - MAX_ALERTS_PER_USER_PER_DAY = 10
  - Alert pause được qua /pause <id> <duration>
```

---

# 🤖 Telegram Commands

```text
/start         giới thiệu + ngôn ngữ
/search        wizard tìm vé
/watch         tạo alert
/alerts        liệt kê alert
/pause <id>    tạm dừng alert
/delete <id>   xoá alert
/deals         top deal hôm nay
/history       lịch sử giá tuyến
/digest        bật/tắt daily digest (V0.4)
/help
```

Vẫn hỗ trợ nhập tự nhiên (không cần command).

---

# 🔐 Environment Variables

```env
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_MODE=polling          # polling|webhook
TELEGRAM_WEBHOOK_URL=

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/airdeal.db

# Providers
TRAVELOKA_AFFILIATE_ID=
TRIP_AFFILIATE_ID=
VEXERE_ENABLED=false
ATADI_ENABLED=false

# Scraper (optional)
PROXY_URL=
USER_AGENT_POOL=

# LLM (V0.3, optional)
USE_LLM_PARSER=false
ANTHROPIC_API_KEY=
LLM_DAILY_COST_CAP_USD=2.0

# Worker
PRICE_SCAN_INTERVAL_MINUTES=60
SEARCH_CACHE_TTL_MINUTES=30
MAX_ALERTS_PER_USER_PER_DAY=10
RATE_LIMIT_PER_MINUTE=20

# Observability (V0.5)
SENTRY_DSN=
PROMETHEUS_PORT=9090
LOG_LEVEL=INFO
```

---

# 🐳 Docker Compose

```yaml
services:
  airdeal-bot:
    build: .
    container_name: airdeal-vn-bot
    restart: unless-stopped
    env_file: [.env]
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    ports:
      - "8080:8080"
```

---

# 🚀 Run Local

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # nếu bật scraper Playwright
python -m app.main
```

Docker:

```bash
docker compose up -d --build
docker compose logs -f airdeal-bot
```

---

# 🧪 Test Strategy

Chi tiết edge cases: [SPEC.md](SPEC.md) §4.

```bash
pytest tests/ -v
pytest tests/nlp/ --cov=app/nlp     # parser cần coverage >= 90%
pytest tests/alerts/                # alert logic phải có golden test
```

Golden tests bắt buộc:
* `tests/nlp/test_parser_golden.py` — 50+ câu thật user
* `tests/alerts/test_dedup.py` — mọi nhánh trigger/dedup
* `tests/deals/test_scoring_baseline.py` — baseline percentile

---

# 🧭 Roadmap

### V0.1 — MVP "chạy được"
Bot phản hồi tự nhiên + tìm vé + alert với 1 provider VN thật.
Output: deploy được, 10 beta user dùng được 1 tuần.

### V0.2 — Đa provider + deal thật
Fanout 3 provider, cache, baseline percentile, affiliate ref.
Output: bot báo "rẻ nhất" mà user mở Traveloka không tìm thấy rẻ hơn.

### V0.3 — NLP nâng cao + Conversational UX
LLM fallback, ConversationHandler, inline keyboard, flexible date, filter.
Output: user gõ bất cứ gì cũng hiểu.

### V0.4 — Price prediction "nên mua hay chờ"
Module `predict/`, daily digest, multi-leg route.
Output: feature khác biệt — user trust bot hơn tự search.

### V0.5 — Production hardening
Postgres, Redis, Celery, proxy pool, Sentry, Prometheus, CI/CD.
Output: chịu 1k+ DAU, alert delivery >= 99%.

### V1.0 — Multi-channel + Monetization
Zalo bot, web app, affiliate dashboard, admin panel, subscription tier, public API.
Output: sản phẩm thật, có doanh thu affiliate.

---

# 🧑‍💻 Development Rule

* Không code tính năng đặt vé/thanh toán/đăng nhập hãng bay.
* Bot chỉ làm: **Search → Compare → Alert → Send booking link**.
* Mọi quyết định kiến trúc lớn → ADR trong [docs/adr/](docs/adr/).
* Mọi tính năng user-facing → cập nhật [SPEC.md](SPEC.md) trước khi code.
* AI agent đọc [AGENTS.md](AGENTS.md) trước khi sinh code.

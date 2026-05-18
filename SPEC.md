# SPEC — AirDeal VN Bot

Spec chi tiết cho MVP V0.1. Mọi feature mới phải bổ sung section ở đây trước khi viết code.

> Tham chiếu: [README.md](README.md) (architecture), [AGENTS.md](AGENTS.md) (agent rule), [docs/adr/](docs/adr/) (kiến trúc).

---

## 1. Glossary

| Thuật ngữ | Định nghĩa |
|---|---|
| `flight_key` | `sha1(airline + "|" + flight_number + "|" + departure_date + "|" + depart_time)`. Khoá định danh chuyến bay cross-provider. |
| `baseline` | `price_snapshots` cùng route + ±7 ngày trong 30 ngày gần nhất. |
| `is_deal` | `price <= P25(baseline)`. |
| `is_great_deal` | `price <= P15(baseline)`. |
| `days_to_departure` | `departure_date - today` (số ngày). |
| `cache_key` | `sha1(origin|destination|departure_date|return_date|adults|children|infants)`. |

---

## 2. Telegram Commands — Acceptance Criteria

### 2.1 `/start`

**AC1**. Bot reply trong < 2s với tin chào tiếng Việt + 3 ví dụ search.
**AC2**. Insert/upsert user vào bảng `users` (theo `telegram_id`).
**AC3**. Log event `user_start` với `telegram_id`, không log username/full_name ở info level.

**Edge cases**:
- User bấm `/start` lần 2 → không tạo row mới, không reset alert.
- User block bot rồi unblock → vẫn chạy bình thường.

### 2.2 `/search` (hoặc nhập tự nhiên)

**AC1**. Parser trả về object hợp lệ → gọi `flight_service.search()` → reply top 3–5 offer trong < 8s (P95).
**AC2**. Parser không hiểu → reply gợi ý format + ví dụ.
**AC3**. Provider tất cả đều fail → reply "không tìm được, thử lại sau" + log error, không crash.
**AC4**. Mỗi offer hiển thị: airline, flight_number (nếu có), depart→arrive, giá/người + tổng, badge deal nếu `is_deal`, booking link affiliate.
**AC5**. Nếu có baseline đủ data (≥ 10 snapshot trong 30d) → hiển thị "rẻ hơn X% median".

**Edge cases**:
- Date trong quá khứ → reply "ngày đã qua, vui lòng nhập ngày tương lai".
- Date > 360 ngày → reply "chỉ tìm được vé trong 360 ngày".
- Origin == destination → reply "điểm đi và đến phải khác nhau".
- Origin/destination không có trong alias → reply "chưa hỗ trợ sân bay X, các sân bay hỗ trợ: …".
- Passengers > 9 → reply "tối đa 9 khách/lần search".
- Infants > Adults → reply "số em bé không vượt quá người lớn".

### 2.3 `/watch <route> <max_price>` (hoặc qua wizard)

**AC1**. Tạo row trong `alerts` với `active=1`.
**AC2**. Nếu user đã có ≥ 10 alert active → reply "đạt giới hạn, xoá bớt trước".
**AC3**. Reply confirm với ID alert + tóm tắt điều kiện.
**AC4**. Worker scheduler pick up trong vòng `PRICE_SCAN_INTERVAL_MINUTES`.

**Edge cases**:
- Cùng route + date + price → upsert thay vì insert duplicate.
- `max_price` < 100k hoặc > 50tr → reject với message.

### 2.4 `/alerts`

**AC1**. List tối đa 20 alert active của user, mỗi alert 1 dòng compact.
**AC2**. Mỗi dòng có inline button `Pause` / `Delete`.

### 2.5 `/pause <id> <duration>`

**AC1**. Validate alert thuộc user. Nếu không → "alert không tồn tại".
**AC2**. Parse duration: `1h`, `1d`, `7d`. Set `paused_until = now + duration`.
**AC3**. Worker bỏ qua alert có `paused_until > now`.

### 2.6 `/delete <id>`

**AC1**. Validate ownership.
**AC2**. Set `active=0` (soft delete, giữ cho history).

### 2.7 `/deals`

**AC1**. Trả top 5 `is_great_deal` trong 24h qua, ưu tiên route user từng search/watch.
**AC2**. Nếu chưa đủ data → reply "chưa đủ dữ liệu, quay lại sau".

### 2.8 `/history <route>`

**AC1**. Vẽ text-based sparkline 30 ngày giá median + min của route.
**AC2**. Nếu < 7 snapshot → reply "chưa đủ data".

### 2.9 `/help`

**AC1**. List tất cả command + 3 ví dụ nhập tự nhiên.

---

## 3. NLP Parser — AC & Edge Cases

### 3.1 Required parse fields

```python
class ParsedQuery(BaseModel):
    intent: Literal["search_cheapest", "watch", "history", "unknown"]
    trip_type: Literal["one_way", "round_trip"] | None
    origin: str | None              # IATA code
    destination: str | None
    departure_date: date | None
    return_date: date | None
    passengers: PassengerCount
    max_price_per_person: int | None
    filters: dict = {}              # cabin_class, time_of_day, airline...
    raw_text: str
    confidence: float               # 0..1
```

### 3.2 Vietnamese date AC

| Input | Resolve (today = 2026-05-17) |
|---|---|
| `hôm nay` | 2026-05-17 |
| `mai` | 2026-05-18 |
| `mốt` | 2026-05-19 |
| `kia` / `ngày kia` | 2026-05-20 |
| `thứ 2 tuần sau` | 2026-05-25 |
| `cuối tuần này` | 2026-05-24 (CN gần nhất, nếu hôm nay là CN thì là 2026-05-24) |
| `đầu tháng 6` | 2026-06-01..2026-06-05 (range) |
| `giữa tháng 6` | 2026-06-13..2026-06-17 |
| `cuối tháng 6` | 2026-06-25..2026-06-30 |
| `20/5` | nearest future 2026-05-20 hoặc 2027-05-20 nếu đã qua |
| `20-5-2026` | 2026-05-20 |
| `20 tháng 5` | 2026-05-20 (nearest future) |

### 3.3 Origin/destination AC

- Match longest alias trước (`"hồ chí minh"` ưu tiên hơn `"hồ"`).
- Không phân biệt hoa thường, có/không dấu, có/không khoảng trắng thừa.
- Hỗ trợ pattern: `"<A> đi <B>"`, `"<A> -> <B>"`, `"<A> <B>"`, `"từ <A> tới <B>"`, `"bay <B>"` (origin = HAN default cho V0.1, V0.3 sẽ infer từ user history).

### 3.4 Passenger AC

| Input | adults | children | infants |
|---|---|---|---|
| `1 người` / `1 khách` / không nói | 1 | 0 | 0 |
| `2 người` | 2 | 0 | 0 |
| `2 vợ chồng` / `2vc` | 2 | 0 | 0 |
| `2vc 1 bé` | 2 | 1 | 0 |
| `2 người lớn 1 trẻ em 1 em bé` | 2 | 1 | 1 |
| `gia đình 4` | 2 | 2 | 0 (assumption — confirm với user) |

### 3.5 Edge cases parser

- Unicode normalize (NFC) trước khi match.
- Strip ký tự đặc biệt nhưng giữ `/-:`.
- Input toàn emoji / quá ngắn (< 4 char) → `intent=unknown, confidence=0`.
- Input > 500 char → reject (rate limit + DoS guard).
- Sai chính tả phổ biến: `"sai gon"`, `"saigon"`, `"hà nôi"`, `"danang"` — đều phải match.
- Nếu input có cả label ngày đi (`đi` / `di` / `bay`) và ngày về (`về` / `ve`) → parse `trip_type=round_trip`, giữ đúng `departure_date` và `return_date` theo label.
- Nếu ngày đi và ngày về trùng nhau nhưng có đủ label `đi/về` → vẫn parse là khứ hồi cùng ngày, không gộp thành one-way.
- Hai date xuất hiện không có `đi/về` → assume round_trip, smaller=departure, larger=return.

---

## 4. Provider — AC & Failure Modes

### 4.1 Provider contract

- `search()` phải trả về `list[FlightOffer]` (có thể rỗng).
- Timeout cứng 8 giây/provider. Quá → raise `ProviderTimeout`, fanout không bị block.
- Retry: max 2, exponential backoff (1s, 3s), chỉ retry trên network error / 5xx.
- Mọi exception khác → log + skip provider, không crash search.
- `booking_url` phải đã inject affiliate ref nếu có.

### 4.2 Fanout & merge

- `asyncio.gather(*providers, return_exceptions=True)`.
- Merge bằng `flight_key`. Nếu trùng → giữ offer có `price_per_person` thấp nhất.
- Nếu ≥ 1 provider thành công → trả kết quả. Nếu tất cả fail → raise `AllProvidersFailed`.

### 4.3 Cache

- Đọc cache trước khi fanout. Hit → trả luôn.
- Miss → fanout → ghi cache với `expires_at = now + SEARCH_CACHE_TTL_MINUTES`.
- Cache hỏng (JSON parse fail) → treat as miss + xoá row.
- V0.2: sau search thành công, bot ghi `price_snapshots` từ offers trả về để build baseline từ cả search thường lẫn alert scan.

### 4.4 Provider-specific (V0.1)

**Traveloka affiliate**: API chính thức nếu được approve. Field map: `price.amount → price_per_person`.
**Vexere/Atadi scraper**: HTML parse với BeautifulSoup. User-agent rotation từ pool. Nếu detect captcha → log + skip.

### 4.5 Provider-specific (V0.2)

- Provider có booking URL thật phải trả `booking_url` đã inject affiliate nếu có.
- Provider chỉ có giá/chuyến bay, không có booking URL trực tiếp, được trả link tìm kiếm an toàn nhưng UI phải label là link tìm vé, không label là đặt vé.

---

## 5. Deal Scoring — AC

### 5.1 Baseline

```python
def baseline(origin, destination, departure_date) -> Stats:
    # Snapshots cùng route, departure_date ± 7 ngày, created_at trong 30 ngày
    rows = query(...)
    if len(rows) < 10:
        return Stats(insufficient=True)
    return Stats(
        p15=percentile(rows.price, 15),
        p25=percentile(rows.price, 25),
        p50=percentile(rows.price, 50),
        p75=percentile(rows.price, 75),
        count=len(rows),
    )
```

### 5.2 Score formula

```python
score = 0.6 * (1 - price_pct/100) + 0.25 * time_score + 0.15 * airline_trust
```

- `price_pct`: rank của offer.price trong baseline (0–100).
- `time_score`: 1.0 nếu 06:00–22:00, 0.5 khác.
- `airline_trust`: dict cố định trong `app/deals/scoring.py`.

### 5.3 AC

- Baseline insufficient → vẫn rank theo price, không hiện badge deal.
- Score tie → tie-break bằng price thấp hơn, sau đó depart_time sớm hơn.

---

## 6. Alert Worker — AC & Failure Modes

### 6.1 Loop

```text
Mỗi PRICE_SCAN_INTERVAL_MINUTES:
  unique_routes = SELECT DISTINCT (origin, destination, departure_date)
                  FROM alerts WHERE active=1 AND (paused_until IS NULL OR paused_until < now)
  For each route:
    offers = flight_service.search(route)            # qua cache nếu hit
    For each offer:
      INSERT INTO price_snapshots(...)
    For each alert in route:
      For each offer:
        if should_alert(alert, offer):
          send_telegram(alert.user, offer)
          INSERT INTO sent_notifications(...)
```

### 6.2 `should_alert` AC

```python
def should_alert(alert, offer) -> bool:
    if not within_daily_quota(alert.user_id):
        return False
    if recently_sent(alert.id, offer.flight_key, hours=6):
        last_price = get_last_sent_price(alert.id, offer.flight_key)
        if offer.price_per_person > last_price * 0.9:   # giảm < 10% so với lần trước
            return False
    if offer.price_per_person <= alert.max_price_per_person:
        return True
    if price_drop_pct(offer) >= 5:
        return True
    if is_great_deal(offer):
        return True
    return False
```

### 6.3 Failure modes

- Telegram API 429 → backoff + retry.
- DB lock (SQLite) → WAL mode + retry 3 lần.
- Worker crash → systemd/Docker restart. Job idempotent (dedup bằng `sent_notifications`).

---

## 7. Security AC

- `TELEGRAM_BOT_TOKEN` & API key không bao giờ log.
- Webhook verify `X-Telegram-Bot-Api-Secret-Token` == `TELEGRAM_WEBHOOK_SECRET`.
- Per-user rate limit: 20 message/phút (token bucket trong memory, V0.5 chuyển Redis).
- Input length > 500 char → reject.
- DB query 100% parameterised (`aiosqlite` placeholder, không string concat).
- Booking URL trước khi gửi → validate scheme `https://` + domain whitelist.

---

## 8. Observability AC

- `structlog` JSON output. Required fields: `timestamp`, `level`, `event`, `request_id`, `user_id` (nếu có).
- Mỗi search có `request_id` (uuid4), trace qua handler → service → provider.
- `/health` endpoint trả `{status:"ok", db:"ok", providers: {...}}`.
- Counter metric (V0.5): `search_total`, `search_latency_seconds`, `alert_sent_total`, `provider_error_total{provider=...}`.

---

## 9. Non-Functional Requirements

| Metric | Target V0.1 | Target V0.5 |
|---|---|---|
| Search P95 latency | < 8s | < 4s |
| Alert delivery delay | < 70 phút | < 5 phút |
| Bot uptime | 95% | 99.5% |
| Parser accuracy (golden) | ≥ 80% | ≥ 95% |
| Concurrent users | 50 | 1000 |
| DB size | < 500MB | unbounded (Postgres) |

---

## 10. Out of Scope (mọi version)

- Tự động đặt vé.
- Thanh toán / lưu thẻ.
- Đăng nhập tài khoản hãng bay.
- Vé quốc tế (V1.x cân nhắc).
- Crawl quá 3 site cùng lúc cho 1 search.

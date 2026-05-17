# AGENTS.md — Hướng dẫn cho AI Agent

Tài liệu này định nghĩa cách AI agent (Claude Code, Codex, Cursor, …) phải làm việc trên repo `airdeal-vn-bot`. Đọc file này trước khi sinh code, sửa code, hoặc tạo task.

---

## 1. Mục tiêu sản phẩm (KHÔNG được đi chệch)

AirDeal VN Bot là **bot Telegram săn vé máy bay nội địa Việt Nam giá rẻ**.

Bot CHỈ làm:

```
Search → Compare → Alert → Send booking link
```

Bot KHÔNG bao giờ:

- Tự đặt vé
- Xử lý thanh toán
- Đăng nhập tài khoản hãng bay thay user
- Crawl ồ ạt nhiều site cùng lúc
- Trở thành "AI agent phức tạp" ngoài scope MVP

Nếu user/PR yêu cầu thêm tính năng nằm ngoài 4 bước trên → **STOP, hỏi lại**, đừng âm thầm implement.

Tham chiếu chi tiết scope, schema DB, provider interface, alert logic: [README.md](README.md).

---

## 2. Nguyên tắc cốt lõi (áp dụng mọi lúc)

Lấy từ [.skills/using-agent-skills/SKILL.md](.skills/using-agent-skills/SKILL.md):

1. **Surface assumptions** — Trước khi code phần non-trivial, liệt kê assumption và chờ confirm.
2. **Manage confusion actively** — Gặp mâu thuẫn giữa spec và code → STOP, hỏi, không tự đoán.
3. **Push back when warranted** — Không phải yes-machine. Thấy approach sai thì nói thẳng + đề xuất alternative.
4. **Enforce simplicity** — Boring code > clever code. 100 dòng đủ thì không viết 1000 dòng.
5. **Scope discipline** — Chỉ sửa đúng thứ được yêu cầu. Không "dọn dẹp" code ngoài task. Không xoá comment/code mình không hiểu.
6. **Verify, don't assume** — Task chỉ done khi có bằng chứng (test pass, log chạy thật).

---

## 3. Quy trình bắt buộc theo loại task

Trước khi bắt đầu, agent **phải xác định loại task** và chọn skill từ [.skills/](.skills/):

| Loại task | Skill bắt buộc đọc trước |
|-----------|--------------------------|
| Ý tưởng mơ hồ, chưa rõ scope | `idea-refine` |
| Tính năng/module mới | `spec-driven-development` → `planning-and-task-breakdown` |
| Implement code | `incremental-implementation` (+ `context-engineering`) |
| Thiết kế API/provider interface | `api-and-interface-design` |
| Cần check tài liệu thư viện (telegram-bot, FastAPI, Playwright, Amadeus, …) | `source-driven-development` |
| Quyết định kiến trúc / lựa chọn rủi ro cao | `doubt-driven-development` |
| Viết / chạy test | `test-driven-development` |
| Test Playwright / browser scraping | `browser-testing-with-devtools` |
| Bug / lỗi runtime | `debugging-and-error-recovery` |
| Review code trước khi merge | `code-review-and-quality` |
| Đụng tới input user / token / DB query | `security-and-hardening` |
| Tối ưu tốc độ / latency provider | `performance-optimization` |
| Commit / branch | `git-workflow-and-versioning` |
| GitHub Actions / Docker build pipeline | `ci-cd-and-automation` |
| Viết ADR / docs | `documentation-and-adrs` |
| Release / deploy Docker | `shipping-and-launch` |
| Code đã tồn tại cần gọn hơn | `code-simplification` |
| Bỏ provider cũ / đổi API | `deprecation-and-migration` |

Workflow điển hình cho 1 feature mới:

```
spec-driven-development
  → planning-and-task-breakdown
    → incremental-implementation
      → test-driven-development
        → code-review-and-quality
          → git-workflow-and-versioning
```

Bug fix tối thiểu: `debugging-and-error-recovery` → `test-driven-development` → `code-review-and-quality`.

---

## 4. Ràng buộc kỹ thuật của repo

### Stack (cố định trong MVP)

Python 3.11+, `python-telegram-bot`, FastAPI, APScheduler, httpx, Playwright, BeautifulSoup4, lxml, SQLite, Docker Compose.

**Không** tự ý kéo PostgreSQL / Redis / Celery / LLM API vào MVP. Đó là roadmap V0.4.

### Cấu trúc thư mục

Tuân thủ layout trong [README.md](README.md) section "📁 Project Structure". Không tạo top-level package mới nếu chưa thảo luận.

### Provider interface

Mọi flight provider **phải** implement đúng `FlightProvider.search(...)` và trả về `list[FlightOffer]` với đầy đủ field như spec README. Không tạo format riêng cho từng provider.

### NLP

- Ưu tiên **regex parser** trước. LLM parser chỉ bật khi `USE_LLM_PARSER=true`.
- Mọi địa danh tiếng Việt phải đi qua `AIRPORT_ALIASES`. Không hard-code mã sân bay rải rác.

### Alert logic (không được sửa nếu không có lý do rõ ràng)

- Gửi alert khi: `price <= max_price_per_person` HOẶC giảm ≥ 5% so với lần trước.
- Dedup: cùng `flight_key` không gửi lại trong 6 giờ.
- Trần: `MAX_ALERTS_PER_USER_PER_DAY` (mặc định 10).

### Database

- MVP dùng SQLite. Schema tham chiếu README. Mọi thay đổi schema phải có migration trong `app/db/migrations/`.
- Không chạy raw SQL với string concatenation từ input user → security risk.

### Secret / Env

- Đọc qua `app/config.py`. Không hard-code token.
- Không log `TELEGRAM_BOT_TOKEN`, `AMADEUS_*`, `KIWI_API_KEY`, `OPENAI_API_KEY`.
- File `.env` không bao giờ được commit. Chỉ cập nhật `.env.example`.

---

## 5. Quy tắc viết code

- **Tiếng Việt cho user-facing strings** (tin nhắn Telegram, lỗi hiển thị). Code, identifier, comment kỹ thuật dùng tiếng Anh.
- **Async-first**: handler Telegram, provider, HTTP call dùng `async`/`await`. Không block event loop bằng `requests` hay `time.sleep`.
- **Type hints bắt buộc** cho public function/method.
- **Không bắt `except Exception:` câm**. Log có context hoặc re-raise.
- **Comment**: chỉ viết khi giải thích "tại sao", không phải "cái gì". Không viết docstring nhiều đoạn.
- **Test**: feature mới phải có test trong `tests/`. Parser và alert logic là 2 vùng bắt buộc test kỹ.

---

## 6. Verification trước khi báo "done"

Một task chỉ được coi là hoàn thành khi:

1. Code chạy được local (`python -m app.main` hoặc test runner).
2. Test liên quan pass.
3. Không có secret/token bị log hoặc commit.
4. Nếu sửa schema DB → có migration.
5. Nếu thêm dependency → đã thêm vào `requirements.txt` và giải thích lý do.
6. Nếu thay đổi behavior người dùng nhìn thấy → đã cập nhật phần tương ứng trong [README.md](README.md).

Báo "seems to work" mà không có evidence = **failure**.

---

## 7. Khi không chắc

Đọc skill liên quan trong [.skills/](.skills/) trước. Nếu vẫn không chắc → hỏi user, đừng đoán. Spec mâu thuẫn với code hiện tại → hỏi cái nào ưu tiên.

Mục tiêu cuối: bot nhỏ, gọn, đáng tin, đúng scope MVP. Không phình to.

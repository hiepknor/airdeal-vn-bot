# ADR-0003: NLP strategy — regex-first, LLM fallback có cost cap

- **Status**: Accepted
- **Date**: 2026-05-17
- **Deciders**: hiepknor

## Context

Bot nhận câu tiếng Việt tự nhiên với độ biến thể rất cao:

- Có dấu / không dấu / viết tắt (`hn`, `sg`, `đn`).
- Thời gian tương đối (`mai`, `cuối tuần`, `đầu tháng 6`).
- Cấu trúc câu lộn xộn (`"2vc 1 bé bay sg cuối tuần này"`).
- Sai chính tả (`"sai gon"`, `"hà nôi"`).

Hai cực:

- **Pure regex**: nhanh, miễn phí, deterministic, nhưng phủ kém — user input lạ là fail.
- **Pure LLM** (Claude/Gemini): hiểu tốt, nhưng latency 1–3s/call + cost. Với 1000 search/ngày × $0.001 = $1/ngày = $30/tháng — tolerable nhưng có thể bị attack đẩy lên 100x.

## Decision

### Pipeline thứ tự

```
input
  │
  ├─→ regex_parser (V0.1, free, < 5ms)
  │       │
  │       ├─ confidence >= 0.7 → DONE
  │       └─ confidence <  0.7 → fallback
  │
  ├─→ dates_vi.resolve (V0.1)         # luôn chạy để resolve thời gian tương đối
  │
  └─→ llm_parser (V0.3, có cost cap)
          - chỉ bật khi USE_LLM_PARSER=true
          - check LLM_DAILY_COST_CAP_USD trước mỗi call
          - dùng Claude Haiku 4.5 (rẻ nhất + nhanh nhất)
          - prompt caching: bật system prompt cache (TTL 5 min)
          - structured output: JSON schema strict
```

### V0.1 implementation

- Regex parser handle: tuyến (origin/destination), số khách, format ngày `dd/mm`, `dd-mm-yyyy`, `dd tháng mm`.
- `dates_vi.py` handle: `mai`, `mốt`, `kia`, `thứ X tuần Y`, `cuối tuần`, `đầu/giữa/cuối tháng N`.
- Confidence scoring: weighted theo số field parse được (origin: 0.3, dest: 0.3, date: 0.3, pax: 0.1).
- Fail → reply gợi ý format, không gọi LLM (V0.1 chưa có).

### V0.3 LLM fallback

- Chỉ trigger khi regex `confidence < 0.7`.
- Cost cap: count Anthropic API spend trong 24h, đạt cap → fallback về reply gợi ý format.
- Prompt: structured output dùng Anthropic SDK `tools` để force JSON.
- Cache: dùng prompt caching cho system prompt (alias map + few-shot).
- Log mỗi LLM call: input length, output, latency, cost ước tính.

### Golden test

Bắt buộc duy trì `tests/nlp/golden_queries.json` với ≥ 50 câu thật:

- Pass V0.1 mục tiêu accuracy ≥ 80%.
- Pass V0.3 (sau LLM) ≥ 95%.

## Consequences

### Tích cực

- V0.1 zero cost NLP, chạy được offline.
- LLM chỉ là safety net → cost predictable.
- Golden test bắt regression khi thêm pattern mới.

### Tiêu cực / Rủi ro

- Regex phình to dần → maintainability giảm. Mitigation: tách `regex_parser` thành các matcher nhỏ test riêng.
- LLM trả JSON không hợp lệ → cần Pydantic validate + fallback gracefully.
- User abuse LLM (gửi câu lạ liên tục) → đốt cost. Mitigation: per-user LLM call limit (10/ngày).

## Alternatives considered

| Phương án | Lý do loại |
|---|---|
| LLM-only từ V0.1 | Cost + latency không phù hợp MVP, dependency Anthropic API |
| Train model NLP riêng (BERT VN) | Cost training + serving cao, không xứng cho task narrow scope |
| Dùng underthesea / pyvi cho tokenize + intent classifier | Đáng cân nhắc cho V0.3, nhưng V0.1 regex đủ |
| Rasa / Dialogflow | Heavy, vendor lock-in |

## References

- [SPEC.md §3](../../SPEC.md) — NLP parser AC
- Claude prompt caching: https://docs.claude.com/en/docs/build-with-claude/prompt-caching

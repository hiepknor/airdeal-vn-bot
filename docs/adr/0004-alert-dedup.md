# ADR-0004: Alert dedup — định nghĩa `flight_key` & threshold gửi lại

- **Status**: Accepted
- **Date**: 2026-05-17
- **Deciders**: hiepknor

## Context

Spec gốc nói "cùng `flight_key` không gửi lại trong 6 giờ" nhưng **không định nghĩa `flight_key`**. Hệ quả:

- Cùng chuyến nhưng provider A trả id `"VJ-123-20260520"`, provider B trả `"vietjet_123_2026/05/20"` → 2 alert cho 1 chuyến.
- Cùng chuyến nhưng đổi giờ bay 15 phút (Vietjet hay đổi schedule) → nên coi là chuyến mới hay không?
- User đặt alert max 1.2tr, giá xuống 1.18tr → gửi. 30 phút sau xuống 1.15tr → có gửi tiếp không?

Cần định nghĩa rõ ràng, deterministic, cross-provider.

## Decision

### Định nghĩa `flight_key`

```python
def make_flight_key(airline: str, flight_number: str | None, departure_date: str, depart_time: str | None) -> str:
    parts = [
        airline.strip().upper(),
        (flight_number or "").strip().upper(),
        departure_date,                         # ISO YYYY-MM-DD
        (depart_time or "").strip(),            # HH:MM, không TZ vì nội địa VN
    ]
    return sha1("|".join(parts).encode()).hexdigest()
```

Lý do **bao gồm `depart_time`**:

- Vietjet thường có 2 chuyến cùng số hiệu trong ngày (sáng + tối) — phải tách.
- Đổi giờ > 0 phút = coi như chuyến mới (an toàn, tránh user mua nhầm chuyến đã shift).

Lý do **không bao gồm `arrive_time` / `price`**:

- Để cùng chuyến từ nhiều provider merge được về 1 row.
- Để track price change qua thời gian (cùng key, snapshot khác nhau).

### Threshold gửi lại

```python
def should_alert(alert, offer) -> bool:
    if not within_daily_quota(alert.user_id):      # MAX_ALERTS_PER_USER_PER_DAY
        return False

    last_sent = get_last_sent(alert.id, offer.flight_key)

    if last_sent and (now - last_sent.sent_at) < 6h:
        # Trong 6 giờ — chỉ gửi lại nếu giá giảm tiếp >= 10%
        if offer.price_per_person > last_sent.price * 0.9:
            return False

    # Trigger điều kiện
    if offer.price_per_person <= alert.max_price_per_person:
        return True
    if price_drop_pct_vs_baseline(offer) >= 5:
        return True
    if is_great_deal(offer):                       # price <= P15
        return True

    return False
```

### Quota

- `MAX_ALERTS_PER_USER_PER_DAY = 10` (configurable).
- Quota tính theo `sent_notifications.sent_at`, scope `user_id`, window rolling 24h.
- Vượt quota → silently skip + log. Không reply user (tránh spam ngược).

### Pause / Unpause

- `alerts.paused_until` (nullable). Worker query `WHERE paused_until IS NULL OR paused_until < now`.
- User pause thủ công qua `/pause <id> <duration>`.
- Auto-pause: alert đã match điều kiện 3 lần trong 24h → auto-pause 6h để tránh spam (V0.4).

## Consequences

### Tích cực

- Dedup deterministic, không phụ thuộc provider.
- Cross-provider merge sạch (cùng key → giữ giá thấp nhất).
- Threshold 10% drop tránh spam nhưng vẫn báo khi giá giảm có ý nghĩa.

### Tiêu cực / Rủi ro

- Provider đổi format `flight_number` (`"VJ123"` vs `"VJ 123"`) → cùng chuyến nhưng khác key. Mitigation: normalize trong provider adapter trước khi gọi `make_flight_key`.
- Vietjet codeshare với Pacific (đã sáp nhập) → cùng chuyến nhưng airline khác nhau. Mitigation: maintain `AIRLINE_ALIASES` trong `flight_key.py`.
- Time-zone: nội địa VN chỉ ICT nên không cần TZ. Nếu V1.x mở quốc tế phải thêm.

### Test bắt buộc

`tests/alerts/test_dedup.py` cover các nhánh:

1. Lần đầu match → gửi.
2. Gửi lại trong 6h, giá giảm < 10% → không gửi.
3. Gửi lại trong 6h, giá giảm ≥ 10% → gửi.
4. Sau 6h → gửi lại bình thường.
5. Vượt quota → không gửi.
6. `flight_key` cross-provider giống nhau → 1 lần gửi.

## Alternatives considered

| Phương án | Lý do loại |
|---|---|
| `flight_key` = provider id | Không cross-provider được |
| `flight_key` không có `depart_time` | Vietjet có 2 chuyến/ngày cùng số → merge sai |
| Threshold gửi lại 5% thay vì 10% | Spam quá, user khó chịu |
| Không có cooldown 6h | Mỗi cycle scan đều gửi → spam |

## References

- [SPEC.md §6](../../SPEC.md) — Alert worker
- [README.md](../../README.md) — Alert logic

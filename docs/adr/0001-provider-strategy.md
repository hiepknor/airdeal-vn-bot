# ADR-0001: Chiến lược chọn flight provider — VN-first, affiliate-first

- **Status**: Accepted
- **Date**: 2026-05-17
- **Deciders**: hiepknor

## Context

Spec gốc đề xuất Amadeus + Kiwi + Google Flights scraper. Thực tế thị trường VN nội địa:

- **Amadeus & Kiwi** cover Vietjet / Bamboo / Vietravel Airlines rất kém. Vietnam Airlines có nhưng giá thường cao hơn 5–15% so với kênh bán trực tiếp / OTA VN.
- **Google Flights** không có Vietjet đầy đủ; scrape vi phạm ToS và bị chặn nhanh.
- Giá rẻ thực tế ở VN nằm tại OTA Việt: **Traveloka, Vexere, Atadi, Abay, Mytour, Trip.com (mạnh Đông Nam Á)** và website hãng.
- Bot báo "rẻ nhất" mà user mở Traveloka thấy rẻ hơn 200–500k → mất uy tín ngay trong tuần đầu vận hành.

Đồng thời cần monetization để nuôi server + proxy — affiliate là lựa chọn tự nhiên (không thu phí user).

## Decision

1. **VN-first**: Provider mặc định là OTA/scraper VN, không phải API quốc tế.
2. **Affiliate-first**: Ưu tiên đăng ký affiliate program chính thức (Traveloka, Trip.com, Booking.com Flights) → API hợp pháp, có ref code → có doanh thu.
3. **Scraper là fallback** chỉ khi affiliate không khả thi (Vexere, Atadi).
4. **Playwright** chỉ dùng cuối cùng cho site SPA chống bot mạnh — lazy load, không bật mặc định.
5. **Provider chain V0.1**: 1 affiliate (Traveloka) + 1 scraper (Vexere hoặc Atadi) + mock provider cho test.
6. **V0.2**: thêm Trip.com affiliate + Atadi → fanout 3 provider song song, merge theo `flight_key`.
7. **Mỗi provider có timeout 8s + retry 2 lần** với `tenacity`; fail không block các provider khác.

## Consequences

### Tích cực

- Giá hiển thị bám sát thị trường VN → user trust cao.
- Affiliate ref → bot tự nuôi, không cần tính phí user.
- Provider chain tách rời → thay/xoá dễ.

### Tiêu cực / Rủi ro

- Phụ thuộc vào việc được approve affiliate (Traveloka khó approve cho dev cá nhân) → cần plan B là scraper.
- Scraper bị break khi site đổi HTML → cần monitoring (provider_error_total metric) + alert oncall.
- Một số tuyến hiếm có thể không có offer nếu cả 3 provider miss → reply gracefully "không tìm được".

### Mitigation

- Có ít nhất 1 affiliate official + 1 scraper backup.
- Mọi provider implement `health_check()` để monitor.
- Sentry alert khi provider error rate > 30% trong 1 giờ.

## Alternatives considered

| Phương án | Lý do loại |
|---|---|
| Chỉ dùng Amadeus | Inventory VN domestic không đủ |
| Chỉ scrape Google Flights | Vi phạm ToS, không có Vietjet đầy đủ, bị block |
| Tự crawl website hãng (vietjetair.com, vietnamairlines.com) | Site SPA chống bot mạnh, cost vận hành cao, vi phạm ToS rõ ràng |
| Mua quyền truy cập GDS (Sabre, Travelport) | Cost > 10k USD/tháng, không phù hợp MVP |

## References

- [SPEC.md §4](../../SPEC.md) — Provider contract
- [README.md](../../README.md) — Architecture diagram

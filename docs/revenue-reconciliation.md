# Đối chiếu báo cáo doanh thu (FR-06)

Ngày đối chiếu: 24/11/2026. API `GET /api/v1/reports/revenue` khớp truy vấn tay ở **8/8 mốc**. Toàn bộ kiểm tra đạt 30/30.

Chạy lại (thư mục `backend/`):

```powershell
python -m scripts.seed_auth
python -m scripts.seed_sales          # 15 đơn mẫu SEED-RV-*, chạy lại không tạo trùng
python -m scripts.check_revenue       # in bảng dưới đây + 30 kiểm tra
```

## Quy tắc tính

- **Doanh thu** gồm:
  - đơn bán `status = 'PAID'`, tính theo `paid_at`;
  - đơn đặt trước `status = 'FULFILLED'` và `payment_status <> 'REFUNDED'`, tính theo `fulfilled_at`.
- **Không tính:** đơn bán CANCELLED (đơn bị hoàn tiền cũng chuyển sang CANCELLED), đơn bán PENDING, đơn đặt trước chưa nhận hàng hoặc đã hoàn tiền.
- **Múi giờ:** `paid_at` / `fulfilled_at` lưu theo UTC, giống cách service POS và đặt trước ghi bằng `UTC_TIMESTAMP()`. Kỳ báo cáo tính theo giờ Việt Nam (UTC+7). Một ngày VN `D` tương ứng khoảng UTC `[D-1 17:00, D 17:00)`.
- **Tuần** bắt đầu thứ Hai, nhãn theo ISO (`2026-W48`). Kỳ không có đơn trả `0`, nên biểu đồ không bị đứt quãng.

## Truy vấn tay

Câu SQL này viết độc lập với code của service: mốc giờ UTC được ghi cứng, không dùng lại hàm nào của API.

```sql
SELECT
  (SELECT COALESCE(SUM(so.total_amount), 0) FROM sales_orders so JOIN branches b ON b.branch_id = so.branch_id
    WHERE so.status = 'PAID' AND so.paid_at >= :utc_from AND so.paid_at < :utc_to [AND b.branch_code = :code])
+ (SELECT COALESCE(SUM(po.total_amount), 0) FROM preorders po JOIN branches b ON b.branch_id = po.branch_id
    WHERE po.status = 'FULFILLED' AND po.payment_status <> 'REFUNDED'
      AND po.fulfilled_at >= :utc_from AND po.fulfilled_at < :utc_to [AND b.branch_code = :code]);
```

Ví dụ ngày 01/11/2026 (giờ VN): `utc_from = '2026-10-31 17:00:00'`, `utc_to = '2026-11-01 17:00:00'`.

## Kết quả

| Mốc | API | Truy vấn tay | Seed tính tay | Khớp | Ghi chú |
|---|---:|---:|---:|:-:|---|
| Ngày 01/11/2026, toàn chuỗi | 400.000 | 400.000 | 400.000 | ✓ | R03 trả 00:30 VN (UTC vẫn là 31/10) + R04 trả 23:59 VN |
| Ngày 02/11/2026, toàn chuỗi | 300.000 | 300.000 | 300.000 | ✓ | R05 trả đúng 00:00 VN |
| Tuần 16-22/11/2026 (W47), CN01 | 120.000 | 120.000 | 120.000 | ✓ | R06 Chủ nhật 23:00 VN |
| Tuần 23-29/11/2026 (W48), CN01 | 180.000 | 180.000 | 180.000 | ✓ | R07 thứ Hai 00:10 VN mở tuần mới |
| Tháng 11/2026, CN02 (MANAGER) | 950.000 | 950.000 | 950.000 | ✓ | R04 + R05 + đặt trước P01 |
| Tháng 12/2026, CN03 | 350.000 | 350.000 | 350.000 | ✓ | P02 nhận hàng 01:00 VN ngày 01/12 (UTC còn là 30/11) |
| Năm 2025, toàn chuỗi | 200.000 | 200.000 | 200.000 | ✓ | Chỉ R02; R01 trả 00:30 VN ngày 01/01/2026 |
| Năm 2026, toàn chuỗi | 2.350.000 | 2.350.000 | 2.350.000 | ✓ | |

## Đơn không được tính

Kết quả kiểm tra: không kỳ nào chứa các số tiền dưới đây.

| Đơn | Trạng thái | Số tiền |
|---|---|---:|
| X01 | Đơn bán CANCELLED (đã trả rồi hoàn tiền) | 777.000 |
| X02 | Đơn bán PENDING | 666.000 |
| X03 | Đặt trước FULFILLED, thanh toán REFUNDED | 888.000 |
| X04 | Đặt trước READY (đã trả tiền, chưa nhận hàng) | 555.000 |
| X05 | Đặt trước CANCELLED | 444.000 |

Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-05, server CẤU HÌNH A (SMS sandbox). |
| **Dữ liệu đầu vào (seed)** | Nhập kho thêm 1 chiếc Áo khoác gió Đen / M, ghi chú Hàng về đợt 2 |
| **Các bước (giao diện)** | 1. Kho hàng -> Nhập kho: Đen / M, số lượng 1 -> Xác nhận<br>2. Đặt trước: trạng thái B, C<br>3. Dòng B -> Thông báo<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id B}/notifications |
| **Kết quả mong đợi** | B: Đã thông báo, phân bổ 2/2. Lịch sử của B: SMS · 0912***001 · Đã gửi (sandbox, không có tin thật). C: vẫn Chờ hàng 0/1. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 3 / 3 / 0. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: B NOTIFIED 2/2, gửi [('SMS', 'SENT', '', 0)]; C WAITING_STOCK 0/1; tồn (3, 3, 0) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

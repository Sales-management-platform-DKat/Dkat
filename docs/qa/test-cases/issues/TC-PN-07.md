Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-06. ĐỔI SANG CẤU HÌNH B (sai khóa eSMS, email thật). Người test mở hộp thư EMAIL_TEST_TO. |
| **Dữ liệu đầu vào (seed)** | Nhập kho thêm 1 chiếc Áo khoác gió Đen / M, ghi chú Hàng về đợt 3 \| Khách C có SĐT 0912000002 và email EMAIL_TEST_TO |
| **Các bước (giao diện)** | 1. Kho hàng -> Nhập kho: Đen / M, số lượng 1 -> Xác nhận (chờ vài giây)<br>2. Đặt trước: dòng C -> Thông báo<br>3. Mở hộp thư EMAIL_TEST_TO<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id C}/notifications |
| **Kết quả mong đợi** | C: Đã thông báo, 1/1. Lịch sử của C: dòng 1 SMS · Lỗi · AUTH_FAILED; dòng 2 Email · Đã gửi. Hộp thư nhận email '[DKat] Hàng đã về - đơn PD-...: mời đến mua trước dd/mm' gồm 'Áo khoác gió DKat (SKU AK-GIO-DEN-M) x 1: 599.000đ', chi nhánh DKat Quận 1 (12 Lê Lợi...), hạn giữ hàng 7 ngày, 'Tổng tiền: 599.000đ (chưa thanh toán)'. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 4 / 4 / 0. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: C NOTIFIED 1/1, gửi [('SMS', 'FAILED', 'AUTH_FAILED', 0), ('EMAIL', 'SENT', '', 0)]; tồn (4, 4, 0) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

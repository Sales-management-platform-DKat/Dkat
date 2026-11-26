Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | CHẠY LẠI python -m scripts.demo_reset trước TC này (các lần gửi lỗi ở TC-PN-01..03 cũng tính vào giới hạn 5 lần / 10 phút / IP). Server CẤU HÌNH A. |
| **Dữ liệu đầu vào (seed)** | Website, Áo khoác gió DKat Đen / M, chi nhánh DKat Quận 1, tạo 3 đơn theo thứ tự: B = Khách B, 0912000001, 2 Lê Lợi Quận 1, Số lượng 2 \| C = Khách C, 0912000002, email = EMAIL_TEST_TO của .env, 3 Lê Lợi Quận 1, Số lượng 1 \| D = Khách D, 0912000003, 4 Lê Lợi Quận 1, Số lượng 1 |
| **Các bước (giao diện)** | 1. Website: đặt trước lần lượt B, C, D như dữ liệu, ghi lại 3 mã đơn PD-...<br>2. owner01 -> Kho hàng (F5): dòng AK-GIO-DEN-M<br>3. Đặt trước: xem 4 dòng |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders?branchId=1; GET /api/v1/inventory?branchId=1 |
| **Kết quả mong đợi** | Mỗi lần hiện 'Đặt trước thành công' + mã đơn, trạng thái Chờ hàng về; B tạm tính 1.198.000 đ. Trang Đặt trước: Lan, B, C, D đều Chờ hàng. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 0 / 0 / 0 (đặt trước KHÔNG trừ, không giữ kho). |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: B WAITING_STOCK 1198000.00, C WAITING_STOCK, D WAITING_STOCK; tồn AK-GIO-DEN-M CN01 (thực/giữ/khả dụng) = (0, 0, 0) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Như TC-PN-01. |
| **Dữ liệu đầu vào (seed)** | Họ tên Khách B \| Lần 1: SĐT để trống \| Lần 2: SĐT 12345 \| Địa chỉ 2 Lê Lợi, Quận 1 |
| **Các bước (giao diện)** | 1. Form đặt trước Áo khoác gió Đen / M như TC-PN-01<br>2. Nhập Họ tên, để trống SĐT -> Gửi đặt trước<br>3. Nhập SĐT 12345 -> Gửi đặt trước |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders: customer không có phone; rồi phone = "12345" |
| **Kết quả mong đợi** | Cả 2 lần form không gửi, dưới ô SĐT hiện 'Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.' API: 422 INVALID_PREORDER, details[0].field = customer.phone (lần 2 kèm lý do 'Số điện thoại phải có 10–11 chữ số, bắt đầu bằng 0 hoặc dùng mã +84'). |
| **Chạy thử chuẩn bị 25/11** | Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: thiếu -> 422 {'field': 'customer.phone', 'reason': 'Field required'}; '12345' -> 422 customer.phone |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

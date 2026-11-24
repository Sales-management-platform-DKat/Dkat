Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung, server CẤU HÌNH A. Không cần đăng nhập. |
| **Dữ liệu đầu vào (seed)** | Sản phẩm: Áo khoác gió DKat Đen / M (hết hàng) \| Họ tên: (để trống) \| SĐT 0912000001 \| Địa chỉ 2 Lê Lợi, Quận 1 |
| **Các bước (giao diện)** | 1. Mở http://127.0.0.1:5173/#/catalog, chi nhánh DKat Quận 1, ô tìm gõ khoác<br>2. Thẻ Áo khoác gió DKat · Đen / M (Hết hàng) -> Đặt trước<br>3. Để trống Họ tên, nhập SĐT và địa chỉ như dữ liệu -> Gửi đặt trước |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders {"branchId":1,"customer":{"fullName":"","phone":"0912000001","address":"2 Lê Lợi, Quận 1"},"items":[{"variantId":8,"quantity":1}]} |
| **Kết quả mong đợi** | Form không gửi, dưới ô Họ tên hiện 'Vui lòng nhập họ tên.' API: 422, code INVALID_PREORDER, details[0].field = customer.fullName. Không tạo đơn. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

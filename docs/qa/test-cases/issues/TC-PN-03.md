Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Như TC-PN-01. |
| **Dữ liệu đầu vào (seed)** | Lần 1: Khách B, 0912000001, địa chỉ để trống, Đen / M \| Lần 2: Khách B, 0912000001, 2 Lê Lợi, sản phẩm Áo khoác gió Đen / L (còn 6) |
| **Các bước (giao diện)** | 1. Form đặt trước Đen / M, để trống Địa chỉ -> Gửi đặt trước<br>2. Trên danh mục, xem thẻ Áo khoác gió DKat · Đen / L |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders thiếu customer.address; rồi đủ thông tin nhưng items[0].variantId = 9 (Đen / L) |
| **Kết quả mong đợi** | Lần 1: dưới ô Địa chỉ hiện 'Vui lòng nhập địa chỉ.'; API 422, details[0].field = customer.address. Lần 2: thẻ Đen / L ghi Còn hàng, KHÔNG có nút Đặt trước; API 409 VARIANT_IN_STOCK ('Hàng còn đủ; vui lòng mua trực tiếp tại cửa hàng'). Tổng số đơn đặt trước vẫn 1 (chỉ đơn của chị Lan). |
| **Chạy thử chuẩn bị 25/11** | Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff (TC-PA-03), chi nhánh DKat Quận 1. Tồn kho đúng seed. |
| **Dữ liệu đầu vào (seed)** | Sản phẩm: Áo thun cotton DKat Trắng / M (AT-COT-M) x2 + Mũ lưỡi trai DKat Đen (MU-LT-DEN) x1 \| Khách: gõ 0901000001 -> Nguyễn Minh Anh \| Chiết khấu 0 |
| **Các bước (giao diện)** | 1. Bán hàng POS: bấm ô Áo thun cotton DKat Trắng / M 2 lần, ô Mũ lưỡi trai DKat 1 lần<br>2. Ô Tìm khách hàng gõ 0901000001, chọn Nguyễn Minh Anh<br>3. Bấm Tạo đơn chờ thanh toán<br>4. Hộp Xác nhận thanh toán: bấm Để xử lý sau<br>5. Menu Đơn bán: tìm dòng 547.000 đ<br>6. Kho hàng (F5): xem dòng AT-COT-M |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders {"branchId":1,"customerId":1,"items":[{"variantId":2,"quantity":2},{"variantId":7,"quantity":1}]} |
| **Kết quả mong đợi** | Hộp thanh toán hiện Khách cần thanh toán 547.000 đ (2 x 199.000 + 149.000). Sau Để xử lý sau: thông báo 'Đơn bán đã được tạo ở trạng thái chờ thanh toán.' Đơn bán: dòng mã DK-..., khách Nguyễn Minh Anh, 547.000 đ, Chờ thanh toán. Tồn AT-COT-M vẫn 11 (đơn chờ thanh toán chưa trừ kho). API: 201, status PENDING, totalAmount 547000.00. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

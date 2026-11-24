Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cửa sổ trình duyệt): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Có đơn 547.000 đ Chờ thanh toán từ TC-PA-05. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Đơn 547.000 đ của TC-PA-05 \| Phương thức: tiền mặt, số tiền 547.000 đ |
| **Các bước (giao diện)** | 1. Đơn bán: dòng 547.000 đ Chờ thanh toán -> Chi tiết<br>2. Bấm Xác nhận đã nhận tiền mặt<br>3. Đóng hộp, xem trạng thái dòng<br>4. Kho hàng (F5): xem AT-COT-M và MU-LT-DEN |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/confirm-payment {"paymentMethod":"CASH","amount":"547000"} |
| **Kết quả mong đợi** | Đơn chuyển Đã thanh toán; chi tiết ghi Thanh toán: CASH · SUCCESS · 547.000 đ. Tồn CN01: AT-COT-M 11 -> 9, MU-LT-DEN 10 -> 9. API: 200, status PAID. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

### Khi chạy
- [ ] Đã chạy `python -m scripts.demo_reset` (hoặc chạy nối tiếp các TC trước theo thứ tự)
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

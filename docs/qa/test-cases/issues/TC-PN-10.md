Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-09. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Đơn B (2 chiếc, 1.198.000 đ, Đã thông báo) \| Thu tiền mặt đủ 1.198.000 đ |
| **Các bước (giao diện)** | 1. Kho hàng (F5): ghi 3 cột AK-GIO-DEN-M<br>2. Đặt trước: dòng B -> Ghi nhận tiền -> OK<br>3. Kho hàng (F5)<br>4. Đặt trước: dòng B -> Xác nhận giao -> OK<br>5. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders/{id B}/confirm-payment {"paymentMethod":"CASH","amount":"1198000"}; POST .../fulfill {} |
| **Kết quả mong đợi** | Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng): trước 4 / 4 / 0; sau Ghi nhận tiền vẫn 4 / 4 / 0 (thu tiền chưa trừ kho), thanh toán Đã thanh toán; sau Xác nhận giao: B Đã nhận hàng và tồn = 2 / 2 / 0 (trừ 2 chiếc khi giao). |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đơn 547.000 đ Đã thanh toán từ TC-PA-06. Đăng nhập owner01 (cửa sổ thường). |
| **Dữ liệu đầu vào (seed)** | Đơn 547.000 đ của TC-PA-06 \| Lý do: Khách trả hàng |
| **Các bước (giao diện)** | 1. owner01 -> Đơn bán: dòng 547.000 đ Đã thanh toán (khách Nguyễn Minh Anh) -> Chi tiết<br>2. Bấm Hoàn tiền, nhập 'Khách trả hàng', OK<br>3. Đóng hộp, xem trạng thái dòng; mở lại Chi tiết<br>4. Kho hàng (F5): xem AT-COT-M và MU-LT-DEN |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/refund {"reason":"Khách trả hàng"}; gọi lại lần 2 |
| **Kết quả mong đợi** | Dòng chuyển Đã hủy; chi tiết ghi khoản thanh toán CASH · REFUNDED · 547.000 đ. Tồn CN01 hoàn lại: AT-COT-M 9 -> 11, MU-LT-DEN 9 -> 10. API: 200, status CANCELLED, payments[].status = REFUNDED; hoàn lần 2 -> 409. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: 200 đơn CANCELLED, thanh toán ['REFUNDED']; hoàn lần 2 -> 409; tồn AT-COT-M 9 -> 11, MU-LT-DEN 9 -> 10 |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff. Có ít nhất 1 đơn Đã thanh toán ở CN01 (dữ liệu seed có sẵn 53 đơn). |
| **Dữ liệu đầu vào (seed)** | Bất kỳ đơn Đã thanh toán nào ở DKat Quận 1, ví dụ dòng đầu danh sách Đơn bán |
| **Các bước (giao diện)** | 1. staff01 -> Đơn bán: dòng Đã thanh toán đầu tiên -> Chi tiết<br>2. Tìm nút Hoàn tiền |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/refund {"reason":"Thử"} bằng token staff01 |
| **Kết quả mong đợi** | Hộp chi tiết KHÔNG có nút Hoàn tiền (chỉ có ×). API: 403 'Bạn không có quyền thực hiện thao tác này.', đơn vẫn PAID. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

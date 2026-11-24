Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff, giỏ hàng trống. |
| **Dữ liệu đầu vào (seed)** | Quần jean slim Xanh / 29 (QJ-SLIM-29, tồn 11) x1 = 449.000 đ \| Lý do hủy: Khách đổi ý |
| **Các bước (giao diện)** | 1. POS: bấm Quần jean slim Xanh / 29 một lần -> Tạo đơn chờ thanh toán -> Để xử lý sau<br>2. Đơn bán: dòng 449.000 đ Chờ thanh toán (mới nhất) -> Chi tiết<br>3. Bấm Hủy đơn, nhập lý do 'Khách đổi ý', OK<br>4. Kho hàng (F5): xem QJ-SLIM-29 |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/cancel {"reason":"Khách đổi ý"}, rồi thử POST .../confirm-payment |
| **Kết quả mong đợi** | Hộp chi tiết chuyển 'DKat Quận 1 · Đã hủy', không còn nút thu tiền; dòng trong Đơn bán: Đã hủy. Tồn QJ-SLIM-29 vẫn 11. API: hủy 200 status CANCELLED, cancelReason 'Khách đổi ý'; thu tiền đơn đã hủy -> 409. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: hủy -> 200 CANCELLED lý do 'Khách đổi ý'; thu tiền sau khi hủy -> 409; tồn QJ-SLIM-29 11 |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

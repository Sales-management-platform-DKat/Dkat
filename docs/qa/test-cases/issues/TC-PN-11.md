Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-10, server CẤU HÌNH B. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Hủy đơn C (đang giữ 1 chiếc), lý do: Khách không lấy nữa \| Khách D đang chờ (0/1), chỉ có SĐT |
| **Các bước (giao diện)** | 1. Đặt trước: dòng C -> Hủy, nhập lý do -> OK<br>2. Xem trạng thái C và D<br>3. Dòng D -> Thông báo<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders/{id C}/cancel {"reason":"Khách không lấy nữa"}; GET /api/v1/preorders/{id D} |
| **Kết quả mong đợi** | C: Đã hủy. Chiếc của C chuyển ngay cho D: D Sẵn sàng, phân bổ 1/1. Lịch sử của D: SMS · Lỗi · AUTH_FAILED (cấu hình B; D không có email nên D vẫn Sẵn sàng). Job thử lại chạy mỗi 30 giây nên dòng SMS có thể đã hiện 'gửi lại 1..3', sau lần thứ 3 ghi RETRY_EXHAUSTED và dừng. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 2 / 2 / 0 (Lan 1 + D 1). |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: C -> CANCELLED; D READY 1/1 gửi [('SMS', 'FAILED', 'AUTH_FAILED', 0)]; tồn (2, 2, 0) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

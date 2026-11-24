Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Ngay sau TC-PN-07, server CẤU HÌNH B (job thử lại mỗi 30 giây). |
| **Dữ liệu đầu vào (seed)** | Thông báo lỗi có sẵn: Email của chị Lan (NOT_CONFIGURED từ TC-PN-05) và SMS của C (AUTH_FAILED, nhưng C đã nhận email) |
| **Các bước (giao diện)** | 1. Chờ 30-60 giây<br>2. Đặt trước: dòng chị Lan -> Thông báo<br>3. Dòng C -> Thông báo |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id Lan}/notifications và {id C} |
| **Kết quả mong đợi** | Lan: Email · Đã gửi · gửi lại 1 (hộp thư nhóm nhận email); trạng thái đơn Lan chuyển Đã thông báo. C: SMS vẫn Lỗi, KHÔNG được gửi lại (không có 'gửi lại') vì khách đã nhận qua email; không có email thứ 2 gửi cho C. Ghi chú: job chạy lần đầu 30 giây sau khi bật server, nên email của Lan có thể đã được gửi lại ngay trong lúc làm TC-PN-07. |
| **Chạy thử chuẩn bị 25/11** | Đạt (gọi job thử lại trực tiếp; trên server job chạy mỗi NOTIFY_RETRY_INTERVAL_SECONDS) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: lượt thử lại {'checked': 1, 'sent': 1, 'failed': 0, 'skipped': 0}; Lan NOTIFIED 1/1 [('EMAIL', 'SENT', '', 1)]; C [('SMS', 'FAILED', 'AUTH_FAILED', 0), ('EMAIL', 'SENT', '', 0)] |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

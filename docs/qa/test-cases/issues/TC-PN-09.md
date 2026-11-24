Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-08, server CẤU HÌNH B. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Thông báo SMS lỗi của C (AUTH_FAILED) |
| **Các bước (giao diện)** | 1. staff01 -> Đặt trước: dòng C -> Thông báo<br>2. Dòng SMS (Lỗi) -> Gửi lại<br>3. Xem lại dòng SMS<br>4. (API) gửi lại dòng Email đã gửi của C |
| **Kiểm tra nhanh qua API** | POST /api/v1/notifications/{id SMS của C}/resend; POST /api/v1/notifications/{id Email của C}/resend |
| **Kết quả mong đợi** | Sau Gửi lại: dòng SMS vẫn Lỗi (AUTH_FAILED vì khóa sai), hiện 'gửi lại 1'. Dòng Email đã gửi không có nút Gửi lại; API gửi lại SMS -> 200, result FAILED, retryCount 1; gửi lại email đã SENT -> 409 NOTIFICATION_NOT_FAILED. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: gửi lại SMS -> 200 FAILED retryCount 1 (AUTH_FAILED); gửi lại email đã SENT -> 409 NOTIFICATION_NOT_FAILED |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

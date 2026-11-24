Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cửa sổ trình duyệt): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Chưa đăng nhập. |
| **Dữ liệu đầu vào (seed)** | Lần 1: staff01 (thiếu :staff) / DKat@Demo2026 \| Lần 2: owner01 / SaiMatKhau@2026 |
| **Các bước (giao diện)** | 1. Nhập staff01 / mật khẩu đúng, bấm Đăng nhập<br>2. Nhập owner01 / SaiMatKhau@2026, bấm Đăng nhập |
| **Kiểm tra nhanh qua API** | POST /api/v1/auth/login với 2 bộ dữ liệu trên; GET /api/v1/auth/me không gửi token |
| **Kết quả mong đợi** | Cả 2 lần ở lại trang đăng nhập, hộp báo 'Không thể hoàn tất - Tên đăng nhập hoặc mật khẩu không chính xác, hoặc tài khoản đã hết hạn.' API: 401, không có access_token; /auth/me không token -> 401. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

### Khi chạy
- [ ] Đã chạy `python -m scripts.demo_reset` (hoặc chạy nối tiếp các TC trước theo thứ tự)
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

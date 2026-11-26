Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Chưa đăng nhập. |
| **Dữ liệu đầu vào (seed)** | Tên đăng nhập: owner01 \| Mật khẩu: DKat@Demo2026 |
| **Các bước (giao diện)** | 1. Mở http://127.0.0.1:5173/#/login<br>2. Nhập owner01 / mật khẩu<br>3. Bấm Đăng nhập<br>4. Xem menu bên trái và ô chọn chi nhánh ở góc trên |
| **Kiểm tra nhanh qua API** | POST /api/v1/auth/login {"username":"owner01","password":"DKat@Demo2026"} |
| **Kết quả mong đợi** | Vào trang Tổng quan (#/admin/dashboard). Menu đủ 12 mục: Tổng quan, Sản phẩm, Kho hàng, Bán hàng POS, Đơn bán, Đặt trước, Khách hàng, Nhân viên, Báo cáo, Chi nhánh, Thông báo, Cài đặt. Ô chi nhánh có 3 lựa chọn: DKat Quận 1, DKat Cầu Giấy, DKat Hải Châu. API: 200, user.role = owner. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: 200, role=owner, cửa hàng=DKat Fashion, chi nhánh=['DKat Quận 1', 'DKat Cầu Giấy', 'DKat Hải Châu'] |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

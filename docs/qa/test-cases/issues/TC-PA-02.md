Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Dùng cửa sổ InPrivate. |
| **Dữ liệu đầu vào (seed)** | Tên đăng nhập: manager01:manager \| Mật khẩu: DKat@Demo2026 \| manager01 được phân công CN01 + CN02 |
| **Các bước (giao diện)** | 1. Mở #/login trong cửa sổ InPrivate<br>2. Nhập manager01:manager / mật khẩu, bấm Đăng nhập<br>3. Xem menu và ô chọn chi nhánh |
| **Kiểm tra nhanh qua API** | GET /api/v1/inventory?branchId=2 (token manager01) và ?branchId=3 |
| **Kết quả mong đợi** | Vào Tổng quan. Menu 10 mục (KHÔNG có Chi nhánh, Cài đặt). Ô chi nhánh chỉ có DKat Quận 1, DKat Cầu Giấy. API: login 200 role = manager; tồn kho CN02 -> 200; CN03 -> 403. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: 200, role=manager; tồn kho CN02 -> 200, CN03 -> 403 |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

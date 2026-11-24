Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Dùng cửa sổ InPrivate (đăng xuất manager01 nếu đang mở). |
| **Dữ liệu đầu vào (seed)** | Tên đăng nhập: staff01:staff \| Mật khẩu: DKat@Demo2026 \| staff01 thuộc CN01 |
| **Các bước (giao diện)** | 1. Đăng nhập staff01:staff<br>2. Xem trang mở ra đầu tiên, menu, ô chi nhánh<br>3. Gõ thẳng địa chỉ http://127.0.0.1:5173/#/admin/reports |
| **Kiểm tra nhanh qua API** | GET /api/v1/reports/summary?branchId=1 (token staff01) |
| **Kết quả mong đợi** | Mở thẳng Bán hàng POS. Menu 7 mục: Sản phẩm, Kho hàng, Bán hàng POS, Đơn bán, Đặt trước, Khách hàng, Thông báo (KHÔNG có Tổng quan, Báo cáo). Ô chi nhánh chỉ có DKat Quận 1. Mở #/admin/reports: thông báo vai trò này không có màn hình được yêu cầu. API báo cáo -> 403. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

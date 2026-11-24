Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-04, server CẤU HÌNH A. Đăng nhập owner01. |
| **Dữ liệu đầu vào (seed)** | Nhập kho: Áo khoác gió DKat Đen / M, số lượng 2, ghi chú Hàng về đợt 1 |
| **Các bước (giao diện)** | 1. Kho hàng -> Nhập kho: biến thể Áo khoác gió Đen / M, số lượng 2 -> Xác nhận<br>2. Kho hàng (F5): dòng AK-GIO-DEN-M<br>3. Đặt trước: trạng thái 4 đơn<br>4. API: allocatedQuantity của từng đơn<br>5. Dòng chị Lan -> Thông báo |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id} cho Lan, B, C, D -> items[0].allocatedQuantity |
| **Kết quả mong đợi** | Chị Lan (đặt trước nhất): Sẵn sàng, phân bổ 1/1. B: vẫn Chờ hàng, phân bổ 1/2 (nhận phần còn lại). C, D: Chờ hàng, 0/1. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 2 / 2 / 0. Lịch sử thông báo của Lan: Email · Lỗi · NOT_CONFIGURED (cấu hình A tắt email) nên Lan vẫn Sẵn sàng, chưa phải Đã thông báo. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

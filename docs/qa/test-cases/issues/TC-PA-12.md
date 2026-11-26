Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Có token của staff01:staff và manager01:manager (Swagger, Authorize lần lượt từng token). |
| **Dữ liệu đầu vào (seed)** | Áo thun cotton DKat Trắng / L (AT-COT-L, variantId 3) x1 \| staff01: CN02 (id 2) \| manager01: CN03 (id 3) và CN02 (id 2) |
| **Các bước (giao diện)** | 1. (staff01) POST /api/v1/sales-orders {"branchId":2,"items":[{"variantId":3,"quantity":1}]}<br>2. (staff01) GET /api/v1/sales-orders?branchId=2<br>3. (manager01) POST /api/v1/sales-orders với branchId 3<br>4. (manager01) POST với branchId 2, rồi hủy đơn vừa tạo<br>5. Giao diện: manager01 đổi ô chi nhánh sang DKat Cầu Giấy, mở Bán hàng POS |
| **Kiểm tra nhanh qua API** | Như các bước |
| **Kết quả mong đợi** | Bước 1, 2, 3: 403 'Bạn không có quyền truy cập chi nhánh này.' Bước 4: 201 (manager01 được bán ở CN02). Bước 5: POS hiện tồn của DKat Cầu Giấy (ví dụ Áo thun Trắng / L Khả dụng: 10). |
| **Chạy thử chuẩn bị 25/11** | Đạt (API bước 1-4); bước 5 giao diện chưa chạy thử |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: staff01 tạo đơn CN02 -> 403; staff01 xem đơn CN02 -> 403; manager01 tạo đơn CN03 -> 403; manager01 tạo đơn CN02 -> 201 |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

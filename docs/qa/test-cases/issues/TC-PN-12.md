Test case tích hợp **Đặt trước & Thông báo** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cấu hình server): [docs/qa/test-cases/preorder-notify.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/preorder-notify.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-11. Job hết hạn chưa tự chạy trên server (BUG-006): chạy tay. Cần MySQL Workbench hoặc client SQL vào DB dkat_demo. |
| **Dữ liệu đầu vào (seed)** | Đơn chị Lan (Đã thông báo, giữ 1 chiếc, hạn giữ còn 7 ngày) \| Đưa hạn giữ về quá khứ |
| **Các bước (giao diện)** | 1. SQL: UPDATE preorders SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE customer_name = 'Trần Thị Lan';<br>2. backend/: .venv\Scripts\python.exe -m app.workers.preorder_expiry<br>3. Đặt trước (F5): dòng Lan, dòng D<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id Lan} |
| **Kết quả mong đợi** | Lệnh in 'Expired preorders: 1'. Lan: Hết hạn, phân bổ 0/1. D không đổi (Sẵn sàng 1/1). Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 2 / 1 / 1 (chiếc của Lan được giải phóng, không còn ai chờ nên thành khả dụng để bán). |
| **Chạy thử chuẩn bị 25/11** | Đạt (gọi job hết hạn trực tiếp, như bước 2) |

### Khi chạy
- [ ] Đã làm phần Chuẩn bị chung và các test case trước theo thứ tự
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **Đặt trước & Thông báo** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

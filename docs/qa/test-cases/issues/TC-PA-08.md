Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cửa sổ trình duyệt): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff, POS chi nhánh DKat Quận 1, giỏ hàng trống. |
| **Dữ liệu đầu vào (seed)** | Quần jean slim Xanh / 30 (QJ-SLIM-30, tồn 10) x11 \| Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, tồn 0) |
| **Các bước (giao diện)** | 1. Bán hàng POS: bấm ô Quần jean slim Xanh / 30 liên tục 11 lần<br>2. Xem số lượng trong giỏ và thông báo<br>3. Thử bấm ô Áo khoác gió DKat Đen / M<br>4. Bấm Xóa giỏ hàng |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders {"branchId":1,"items":[{"variantId":5,"quantity":11}]} và {"variantId":8,"quantity":1} |
| **Kết quả mong đợi** | Giỏ dừng ở 10, hiện 'Số lượng vượt quá tồn khả dụng.' Ô Áo khoác Đen / M mờ (Khả dụng: 0), không bấm được. API: 409, detail.code = OUT_OF_STOCK, items[].available = 10 (QJ-SLIM-30) và 0 (AK-GIO-DEN-M); không tạo đơn, tồn không đổi. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

### Khi chạy
- [ ] Đã chạy `python -m scripts.demo_reset` (hoặc chạy nối tiếp các TC trước theo thứ tự)
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

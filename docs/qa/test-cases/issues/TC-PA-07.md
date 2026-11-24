Test case tích hợp **POS & Auth** cho vòng kiểm thử Ngày 16. Chuẩn bị chung (seed `demo_reset`, tài khoản, cửa sổ trình duyệt): [docs/qa/test-cases/pos-auth.md](https://github.com/Sales-management-platform-DKat/Dkat/blob/develop/docs/qa/test-cases/pos-auth.md#chuẩn-bị).

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff. Giao diện luôn gửi đúng tổng tiền nên chỉ kiểm tra được qua API (Swagger http://127.0.0.1:8000/docs, Authorize bằng token staff01). |
| **Dữ liệu đầu vào (seed)** | Tạo đơn Quần jean slim Xanh / 31 (QJ-SLIM-31, variantId 6) x1 = 449.000 đ \| Trả sai: 400.000 |
| **Các bước (giao diện)** | 1. POST /api/v1/sales-orders {"branchId":1,"items":[{"variantId":6,"quantity":1}]} -> ghi salesOrderId<br>2. POST /api/v1/sales-orders/{salesOrderId}/confirm-payment {"paymentMethod":"CASH","amount":"400000"}<br>3. GET /api/v1/sales-orders/{salesOrderId}<br>4. Dọn dữ liệu: POST .../cancel {"reason":"Dọn dữ liệu"} |
| **Kiểm tra nhanh qua API** | Như các bước |
| **Kết quả mong đợi** | Bước 2: 422, detail.code = PAYMENT_AMOUNT_MISMATCH, expectedAmount = 449000.00. Bước 3: đơn vẫn PENDING. Tồn QJ-SLIM-31 vẫn 10. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API) |

### Khi chạy
- [ ] Đã chạy `python -m scripts.demo_reset` (hoặc chạy nối tiếp các TC trước theo thứ tự)
- [ ] Ghi Kết quả thực tế, Pass/Fail, Người test, Ngày test vào sheet **POS & Auth** của `docs/qa/DKat_Test_Cases.xlsx`
- [ ] Fail: tạo bug trong `docs/qa/DKat_Bug_Log.xlsx`, ghi mã bug vào comment của issue này
- [ ] Đóng issue khi Pass

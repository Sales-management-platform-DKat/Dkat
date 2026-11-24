# Test case tích hợp POS & Auth (vòng kiểm thử Ngày 16)

Bản Excel: sheet **POS & Auth** trong [DKat_Test_Cases.xlsx](../DKat_Test_Cases.xlsx). Mỗi test case có một GitHub Issue (nhãn `test-case`, `pos-auth`).
Nguồn duy nhất: [pos_auth_cases.py](pos_auth_cases.py), sinh lại bằng `python docs/qa/test-cases/build_test_cases.py`.

## Chuẩn bị

**Chuẩn bị chung (làm 1 lần trước khi chạy TC-PA-01; chạy lại nếu dữ liệu đã bị dùng):**
- 1. git checkout develop && git pull. backend/.env có DB_NAME=dkat_demo (và DB_SSL_MODE=disabled với MySQL cài trên máy), DKAT_ADMIN_TOKEN >= 32 ký tự.
- 2. Trong backend/: python -m scripts.demo_reset (~20 giây) rồi python -m uvicorn app.main:app --port 8000.
- 3. Trong frontend/: .env.local có VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1, VITE_PUBLIC_STORE_ID=1; chạy npm run dev, mở http://127.0.0.1:5173/#/login.
- 4. Mật khẩu mọi tài khoản: DKat@Demo2026. Tên đăng nhập: owner01 | manager01:manager | staff01:staff (nhân viên PHẢI có hậu tố :staff / :manager).
- 5. Mỗi tài khoản một cửa sổ riêng (OWNER cửa sổ thường, nhân viên cửa sổ InPrivate/Ẩn danh): đăng nhập 2 tài khoản trong cùng cửa sổ sẽ đè phiên của nhau.
- 6. Chạy theo thứ tự TC-PA-01 -> 12 (TC-PA-06, 10 dùng đơn tạo ở TC-PA-05). Trước khi đọc tồn kho: mở menu Kho hàng rồi nhấn F5.
- 7. Kiểm tra tự động cùng dữ liệu: python -m scripts.check_pos_auth (sau demo_reset, server đang chạy) in PASS/FAIL 12 test case.

Dữ liệu seed (`python -m scripts.demo_reset`): CN01 DKat Quận 1 (id 1), CN02 DKat Cầu Giấy (id 2), CN03 DKat Hải Châu (id 3).

Tồn / đơn có sẵn ở CN01: Áo thun cotton DKat Trắng / M (AT-COT-M, 199.000 đ) tồn 11; Mũ lưỡi trai DKat Đen (MU-LT-DEN, 149.000 đ) tồn 10; Quần jean slim Xanh / 29 (QJ-SLIM-29, 449.000 đ) tồn 11; Xanh / 30 (QJ-SLIM-30) tồn 10; Xanh / 31 (QJ-SLIM-31) tồn 10; Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, 599.000 đ) tồn 0.

## Danh sách

| ID | Chức năng | Tiêu đề | Issue |
|---|---|---|---|
| [TC-PA-01](#tc-pa-01) | Xác thực | Đăng nhập OWNER | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-01%22) |
| [TC-PA-02](#tc-pa-02) | Xác thực | Đăng nhập MANAGER chỉ thấy chi nhánh được phân công | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-02%22) |
| [TC-PA-03](#tc-pa-03) | Xác thực | Đăng nhập EMPLOYEE chỉ có màn hình bán hàng | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-03%22) |
| [TC-PA-04](#tc-pa-04) | Xác thực | Đăng nhập sai bị từ chối | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-04%22) |
| [TC-PA-05](#tc-pa-05) | POS / Đơn bán | Tạo đơn POS chờ thanh toán | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-05%22) |
| [TC-PA-06](#tc-pa-06) | POS / Đơn bán | Xác nhận thanh toán tiền mặt trừ kho đúng | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-06%22) |
| [TC-PA-07](#tc-pa-07) | POS / Đơn bán | Xác nhận thanh toán sai số tiền bị từ chối (chỉ qua API) | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-07%22) |
| [TC-PA-08](#tc-pa-08) | POS / Đơn bán | Không bán vượt tồn khả dụng | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-08%22) |
| [TC-PA-09](#tc-pa-09) | POS / Đơn bán | Hủy đơn PENDING | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-09%22) |
| [TC-PA-10](#tc-pa-10) | POS / Đơn bán | OWNER hoàn đơn đã thanh toán và hoàn kho | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-10%22) |
| [TC-PA-11](#tc-pa-11) | Phân quyền | EMPLOYEE không hoàn được đơn đã thanh toán | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-11%22) |
| [TC-PA-12](#tc-pa-12) | Phân quyền | Phân quyền theo chi nhánh khi bán hàng | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PA-12%22) |

## TC-PA-01

**Đăng nhập OWNER** (Xác thực)

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Chưa đăng nhập. |
| **Dữ liệu đầu vào (seed)** | Tên đăng nhập: owner01 \| Mật khẩu: DKat@Demo2026 |
| **Các bước (giao diện)** | 1. Mở http://127.0.0.1:5173/#/login<br>2. Nhập owner01 / mật khẩu<br>3. Bấm Đăng nhập<br>4. Xem menu bên trái và ô chọn chi nhánh ở góc trên |
| **Kiểm tra nhanh qua API** | POST /api/v1/auth/login {"username":"owner01","password":"DKat@Demo2026"} |
| **Kết quả mong đợi** | Vào trang Tổng quan (#/admin/dashboard). Menu đủ 12 mục: Tổng quan, Sản phẩm, Kho hàng, Bán hàng POS, Đơn bán, Đặt trước, Khách hàng, Nhân viên, Báo cáo, Chi nhánh, Thông báo, Cài đặt. Ô chi nhánh có 3 lựa chọn: DKat Quận 1, DKat Cầu Giấy, DKat Hải Châu. API: 200, user.role = owner. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-02

**Đăng nhập MANAGER chỉ thấy chi nhánh được phân công** (Xác thực)

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Dùng cửa sổ InPrivate. |
| **Dữ liệu đầu vào (seed)** | Tên đăng nhập: manager01:manager \| Mật khẩu: DKat@Demo2026 \| manager01 được phân công CN01 + CN02 |
| **Các bước (giao diện)** | 1. Mở #/login trong cửa sổ InPrivate<br>2. Nhập manager01:manager / mật khẩu, bấm Đăng nhập<br>3. Xem menu và ô chọn chi nhánh |
| **Kiểm tra nhanh qua API** | GET /api/v1/inventory?branchId=2 (token manager01) và ?branchId=3 |
| **Kết quả mong đợi** | Vào Tổng quan. Menu 10 mục (KHÔNG có Chi nhánh, Cài đặt). Ô chi nhánh chỉ có DKat Quận 1, DKat Cầu Giấy. API: login 200 role = manager; tồn kho CN02 -> 200; CN03 -> 403. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-03

**Đăng nhập EMPLOYEE chỉ có màn hình bán hàng** (Xác thực)

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Dùng cửa sổ InPrivate (đăng xuất manager01 nếu đang mở). |
| **Dữ liệu đầu vào (seed)** | Tên đăng nhập: staff01:staff \| Mật khẩu: DKat@Demo2026 \| staff01 thuộc CN01 |
| **Các bước (giao diện)** | 1. Đăng nhập staff01:staff<br>2. Xem trang mở ra đầu tiên, menu, ô chi nhánh<br>3. Gõ thẳng địa chỉ http://127.0.0.1:5173/#/admin/reports |
| **Kiểm tra nhanh qua API** | GET /api/v1/reports/summary?branchId=1 (token staff01) |
| **Kết quả mong đợi** | Mở thẳng Bán hàng POS. Menu 7 mục: Sản phẩm, Kho hàng, Bán hàng POS, Đơn bán, Đặt trước, Khách hàng, Thông báo (KHÔNG có Tổng quan, Báo cáo). Ô chi nhánh chỉ có DKat Quận 1. Mở #/admin/reports: thông báo vai trò này không có màn hình được yêu cầu. API báo cáo -> 403. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-04

**Đăng nhập sai bị từ chối** (Xác thực)

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung. Chưa đăng nhập. |
| **Dữ liệu đầu vào (seed)** | Lần 1: staff01 (thiếu :staff) / DKat@Demo2026 \| Lần 2: owner01 / SaiMatKhau@2026 |
| **Các bước (giao diện)** | 1. Nhập staff01 / mật khẩu đúng, bấm Đăng nhập<br>2. Nhập owner01 / SaiMatKhau@2026, bấm Đăng nhập |
| **Kiểm tra nhanh qua API** | POST /api/v1/auth/login với 2 bộ dữ liệu trên; GET /api/v1/auth/me không gửi token |
| **Kết quả mong đợi** | Cả 2 lần ở lại trang đăng nhập, hộp báo 'Không thể hoàn tất - Tên đăng nhập hoặc mật khẩu không chính xác, hoặc tài khoản đã hết hạn.' API: 401, không có access_token; /auth/me không token -> 401. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-05

**Tạo đơn POS chờ thanh toán** (POS / Đơn bán)

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff (TC-PA-03), chi nhánh DKat Quận 1. Tồn kho đúng seed. |
| **Dữ liệu đầu vào (seed)** | Sản phẩm: Áo thun cotton DKat Trắng / M (AT-COT-M) x2 + Mũ lưỡi trai DKat Đen (MU-LT-DEN) x1 \| Khách: gõ 0901000001 -> Nguyễn Minh Anh \| Chiết khấu 0 |
| **Các bước (giao diện)** | 1. Bán hàng POS: bấm ô Áo thun cotton DKat Trắng / M 2 lần, ô Mũ lưỡi trai DKat 1 lần<br>2. Ô Tìm khách hàng gõ 0901000001, chọn Nguyễn Minh Anh<br>3. Bấm Tạo đơn chờ thanh toán<br>4. Hộp Xác nhận thanh toán: bấm Để xử lý sau<br>5. Menu Đơn bán: tìm dòng 547.000 đ<br>6. Kho hàng (F5): xem dòng AT-COT-M |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders {"branchId":1,"customerId":1,"items":[{"variantId":2,"quantity":2},{"variantId":7,"quantity":1}]} |
| **Kết quả mong đợi** | Hộp thanh toán hiện Khách cần thanh toán 547.000 đ (2 x 199.000 + 149.000). Sau Để xử lý sau: thông báo 'Đơn bán đã được tạo ở trạng thái chờ thanh toán.' Đơn bán: dòng mã DK-..., khách Nguyễn Minh Anh, 547.000 đ, Chờ thanh toán. Tồn AT-COT-M vẫn 11 (đơn chờ thanh toán chưa trừ kho). API: 201, status PENDING, totalAmount 547000.00. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-06

**Xác nhận thanh toán tiền mặt trừ kho đúng** (POS / Đơn bán)

| | |
|---|---|
| **Điều kiện** | Có đơn 547.000 đ Chờ thanh toán từ TC-PA-05. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Đơn 547.000 đ của TC-PA-05 \| Phương thức: tiền mặt, số tiền 547.000 đ |
| **Các bước (giao diện)** | 1. Đơn bán: dòng 547.000 đ Chờ thanh toán -> Chi tiết<br>2. Bấm Xác nhận đã nhận tiền mặt<br>3. Đóng hộp, xem trạng thái dòng<br>4. Kho hàng (F5): xem AT-COT-M và MU-LT-DEN |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/confirm-payment {"paymentMethod":"CASH","amount":"547000"} |
| **Kết quả mong đợi** | Đơn chuyển Đã thanh toán; chi tiết ghi Thanh toán: CASH · SUCCESS · 547.000 đ. Tồn CN01: AT-COT-M 11 -> 9, MU-LT-DEN 10 -> 9. API: 200, status PAID. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-07

**Xác nhận thanh toán sai số tiền bị từ chối (chỉ qua API)** (POS / Đơn bán)

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff. Giao diện luôn gửi đúng tổng tiền nên chỉ kiểm tra được qua API (Swagger http://127.0.0.1:8000/docs, Authorize bằng token staff01). |
| **Dữ liệu đầu vào (seed)** | Tạo đơn Quần jean slim Xanh / 31 (QJ-SLIM-31, variantId 6) x1 = 449.000 đ \| Trả sai: 400.000 |
| **Các bước (giao diện)** | 1. POST /api/v1/sales-orders {"branchId":1,"items":[{"variantId":6,"quantity":1}]} -> ghi salesOrderId<br>2. POST /api/v1/sales-orders/{salesOrderId}/confirm-payment {"paymentMethod":"CASH","amount":"400000"}<br>3. GET /api/v1/sales-orders/{salesOrderId}<br>4. Dọn dữ liệu: POST .../cancel {"reason":"Dọn dữ liệu"} |
| **Kiểm tra nhanh qua API** | Như các bước |
| **Kết quả mong đợi** | Bước 2: 422, detail.code = PAYMENT_AMOUNT_MISMATCH, expectedAmount = 449000.00. Bước 3: đơn vẫn PENDING. Tồn QJ-SLIM-31 vẫn 10. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API) |

## TC-PA-08

**Không bán vượt tồn khả dụng** (POS / Đơn bán)

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff, POS chi nhánh DKat Quận 1, giỏ hàng trống. |
| **Dữ liệu đầu vào (seed)** | Quần jean slim Xanh / 30 (QJ-SLIM-30, tồn 10) x11 \| Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, tồn 0) |
| **Các bước (giao diện)** | 1. Bán hàng POS: bấm ô Quần jean slim Xanh / 30 liên tục 11 lần<br>2. Xem số lượng trong giỏ và thông báo<br>3. Thử bấm ô Áo khoác gió DKat Đen / M<br>4. Bấm Xóa giỏ hàng |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders {"branchId":1,"items":[{"variantId":5,"quantity":11}]} và {"variantId":8,"quantity":1} |
| **Kết quả mong đợi** | Giỏ dừng ở 10, hiện 'Số lượng vượt quá tồn khả dụng.' Ô Áo khoác Đen / M mờ (Khả dụng: 0), không bấm được. API: 409, detail.code = OUT_OF_STOCK, items[].available = 10 (QJ-SLIM-30) và 0 (AK-GIO-DEN-M); không tạo đơn, tồn không đổi. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-09

**Hủy đơn PENDING** (POS / Đơn bán)

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff, giỏ hàng trống. |
| **Dữ liệu đầu vào (seed)** | Quần jean slim Xanh / 29 (QJ-SLIM-29, tồn 11) x1 = 449.000 đ \| Lý do hủy: Khách đổi ý |
| **Các bước (giao diện)** | 1. POS: bấm Quần jean slim Xanh / 29 một lần -> Tạo đơn chờ thanh toán -> Để xử lý sau<br>2. Đơn bán: dòng 449.000 đ Chờ thanh toán (mới nhất) -> Chi tiết<br>3. Bấm Hủy đơn, nhập lý do 'Khách đổi ý', OK<br>4. Kho hàng (F5): xem QJ-SLIM-29 |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/cancel {"reason":"Khách đổi ý"}, rồi thử POST .../confirm-payment |
| **Kết quả mong đợi** | Hộp chi tiết chuyển 'DKat Quận 1 · Đã hủy', không còn nút thu tiền; dòng trong Đơn bán: Đã hủy. Tồn QJ-SLIM-29 vẫn 11. API: hủy 200 status CANCELLED, cancelReason 'Khách đổi ý'; thu tiền đơn đã hủy -> 409. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-10

**OWNER hoàn đơn đã thanh toán và hoàn kho** (POS / Đơn bán)

| | |
|---|---|
| **Điều kiện** | Đơn 547.000 đ Đã thanh toán từ TC-PA-06. Đăng nhập owner01 (cửa sổ thường). |
| **Dữ liệu đầu vào (seed)** | Đơn 547.000 đ của TC-PA-06 \| Lý do: Khách trả hàng |
| **Các bước (giao diện)** | 1. owner01 -> Đơn bán: dòng 547.000 đ Đã thanh toán (khách Nguyễn Minh Anh) -> Chi tiết<br>2. Bấm Hoàn tiền, nhập 'Khách trả hàng', OK<br>3. Đóng hộp, xem trạng thái dòng; mở lại Chi tiết<br>4. Kho hàng (F5): xem AT-COT-M và MU-LT-DEN |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/refund {"reason":"Khách trả hàng"}; gọi lại lần 2 |
| **Kết quả mong đợi** | Dòng chuyển Đã hủy; chi tiết ghi khoản thanh toán CASH · REFUNDED · 547.000 đ. Tồn CN01 hoàn lại: AT-COT-M 9 -> 11, MU-LT-DEN 9 -> 10. API: 200, status CANCELLED, payments[].status = REFUNDED; hoàn lần 2 -> 409. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-11

**EMPLOYEE không hoàn được đơn đã thanh toán** (Phân quyền)

| | |
|---|---|
| **Điều kiện** | Đăng nhập staff01:staff. Có ít nhất 1 đơn Đã thanh toán ở CN01 (dữ liệu seed có sẵn 53 đơn). |
| **Dữ liệu đầu vào (seed)** | Bất kỳ đơn Đã thanh toán nào ở DKat Quận 1, ví dụ dòng đầu danh sách Đơn bán |
| **Các bước (giao diện)** | 1. staff01 -> Đơn bán: dòng Đã thanh toán đầu tiên -> Chi tiết<br>2. Tìm nút Hoàn tiền |
| **Kiểm tra nhanh qua API** | POST /api/v1/sales-orders/{id}/refund {"reason":"Thử"} bằng token staff01 |
| **Kết quả mong đợi** | Hộp chi tiết KHÔNG có nút Hoàn tiền (chỉ có ×). API: 403 'Bạn không có quyền thực hiện thao tác này.', đơn vẫn PAID. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API + giao diện) |

## TC-PA-12

**Phân quyền theo chi nhánh khi bán hàng** (Phân quyền)

| | |
|---|---|
| **Điều kiện** | Có token của staff01:staff và manager01:manager (Swagger, Authorize lần lượt từng token). |
| **Dữ liệu đầu vào (seed)** | Áo thun cotton DKat Trắng / L (AT-COT-L, variantId 3) x1 \| staff01: CN02 (id 2) \| manager01: CN03 (id 3) và CN02 (id 2) |
| **Các bước (giao diện)** | 1. (staff01) POST /api/v1/sales-orders {"branchId":2,"items":[{"variantId":3,"quantity":1}]}<br>2. (staff01) GET /api/v1/sales-orders?branchId=2<br>3. (manager01) POST /api/v1/sales-orders với branchId 3<br>4. (manager01) POST với branchId 2, rồi hủy đơn vừa tạo<br>5. Giao diện: manager01 đổi ô chi nhánh sang DKat Cầu Giấy, mở Bán hàng POS |
| **Kiểm tra nhanh qua API** | Như các bước |
| **Kết quả mong đợi** | Bước 1, 2, 3: 403 'Bạn không có quyền truy cập chi nhánh này.' Bước 4: 201 (manager01 được bán ở CN02). Bước 5: POS hiện tồn của DKat Cầu Giấy (ví dụ Áo thun Trắng / L Khả dụng: 10). |
| **Chạy thử chuẩn bị 25/11** | Đạt (API bước 1-4); bước 5 giao diện chưa chạy thử |

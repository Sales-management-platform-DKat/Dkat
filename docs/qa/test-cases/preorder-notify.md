# Test case tích hợp Đặt trước & Thông báo (vòng kiểm thử Ngày 16)

Bản Excel: sheet **Đặt trước & Thông báo** trong [DKat_Test_Cases.xlsx](../DKat_Test_Cases.xlsx). Mỗi test case có một GitHub Issue (nhãn `test-case`, `preorder-notify`).
Nguồn duy nhất: [preorder_notify_cases.py](preorder_notify_cases.py), sinh lại bằng `python docs/qa/test-cases/build_test_cases.py`.

## Chuẩn bị

**Chuẩn bị chung (chạy đúng thứ tự TC-PN-01 -> 12 trên seed mới; các TC sau dùng đơn của TC trước):**
- 1. git checkout develop && git pull. backend/.env: DB_NAME=dkat_demo, DB_SSL_MODE=disabled (MySQL trên máy), DKAT_ADMIN_TOKEN >= 32 ký tự, SMTP_* (Gmail App Password) và EMAIL_TEST_TO = hộp thư của người test.
- 2. backend/: python -m scripts.demo_reset (~20 giây). frontend/: .env.local có VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1, VITE_PUBLIC_STORE_ID=1; npm run dev.
- 3. Bật server theo CẤU HÌNH A cho TC-PN-01..06 (PowerShell, trong backend/): $env:ESMS_SANDBOX='true'; $env:SMTP_HOST=''; $env:NOTIFY_RETRY_ENABLED='false'; .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   (SMS sandbox: eSMS kiểm tra yêu cầu nhưng KHÔNG gửi, không tốn tiền; email tắt).
- 4. Trước TC-PN-07 đổi sang CẤU HÌNH B: Ctrl+C rồi trong CỬA SỔ POWERSHELL MỚI: $env:ESMS_API_KEY='SAI-KHOA-KIEM-THU'; $env:NOTIFY_RETRY_INTERVAL_SECONDS='30'; .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   (SMS luôn lỗi AUTH_FAILED, email thật qua SMTP, job thử lại chạy mỗi 30 giây). Không cần đăng nhập lại.
- 5. Tài khoản (mật khẩu DKat@Demo2026): owner01 (cửa sổ thường, nhập kho) và staff01:staff (cửa sổ InPrivate, xử lý đơn). Website khách: http://127.0.0.1:5173/#/catalog.
- 6. Đọc tồn: Kho hàng (F5), dòng AK-GIO-DEN-M, 3 cột Tồn thực / Đã giữ / Khả dụng. Lịch sử thông báo: Đặt trước -> dòng đơn -> nút Thông báo.
- 7. Số lượng đã phân bổ cho từng đơn (ví dụ 1/2) không hiện trên giao diện: xem qua API GET /api/v1/preorders/{id} -> items[0].allocatedQuantity (Swagger http://127.0.0.1:8000/docs, Authorize bằng token owner01).
- 8. Kiểm tra tự động toàn bộ: python -m scripts.demo_reset rồi python -m scripts.check_preorder_notify (không cần bật server; gửi 2 email thật).

Dữ liệu seed (`python -m scripts.demo_reset`): CN01 DKat Quận 1 (id 1), hotline 028 3822 1001.

Tồn / đơn có sẵn ở CN01: Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, variantId 8, 599.000 đ): 0 / 0 / 0. Áo khoác gió DKat Đen / L (AK-GIO-DEN-L, variantId 9): còn 6. Đơn có sẵn: Trần Thị Lan đặt 1 chiếc Đen / M lúc 18:00 hôm qua (xếp hàng số 1), chỉ có email (hộp thư nhóm), chưa thanh toán.

## Danh sách

| ID | Chức năng | Tiêu đề | Issue |
|---|---|---|---|
| [TC-PN-01](#tc-pn-01) | Đặt trước | Thiếu họ tên bị từ chối | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-01%22) |
| [TC-PN-02](#tc-pn-02) | Đặt trước | Thiếu SĐT hoặc SĐT sai định dạng bị từ chối | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-02%22) |
| [TC-PN-03](#tc-pn-03) | Đặt trước | Thiếu địa chỉ bị từ chối; hàng còn thì không cho đặt trước | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-03%22) |
| [TC-PN-04](#tc-pn-04) | Đặt trước | Đặt trước thành công không trừ kho | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-04%22) |
| [TC-PN-05](#tc-pn-05) | Đặt trước | Nhập 2 chiếc -> phân bổ FIFO đúng thứ tự đặt | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-05%22) |
| [TC-PN-06](#tc-pn-06) | Thông báo | Đơn đủ hàng -> READY -> gửi SMS -> Đã thông báo | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-06%22) |
| [TC-PN-07](#tc-pn-07) | Thông báo | SMS lỗi -> tự chuyển sang email | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-07%22) |
| [TC-PN-08](#tc-pn-08) | Thông báo | Thử lại tự động: email lỗi được gửi lại, không gửi trùng | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-08%22) |
| [TC-PN-09](#tc-pn-09) | Thông báo | Gửi lại thủ công bằng nút Gửi lại | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-09%22) |
| [TC-PN-10](#tc-pn-10) | Đặt trước | Xác nhận nhận hàng mới trừ kho | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-10%22) |
| [TC-PN-11](#tc-pn-11) | Đặt trước | Hủy đơn đang giữ hàng -> giải phóng cho khách kế tiếp | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-11%22) |
| [TC-PN-12](#tc-pn-12) | Đặt trước | Hết hạn giữ hàng -> Hết hạn, giải phóng hàng | [tìm issue](https://github.com/Sales-management-platform-DKat/Dkat/issues?q=is%3Aissue+%22TC-PN-12%22) |

## TC-PN-01

**Thiếu họ tên bị từ chối** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Đã làm Chuẩn bị chung, server CẤU HÌNH A. Không cần đăng nhập. |
| **Dữ liệu đầu vào (seed)** | Sản phẩm: Áo khoác gió DKat Đen / M (hết hàng) \| Họ tên: (để trống) \| SĐT 0912000001 \| Địa chỉ 2 Lê Lợi, Quận 1 |
| **Các bước (giao diện)** | 1. Mở http://127.0.0.1:5173/#/catalog, chi nhánh DKat Quận 1, ô tìm gõ khoác<br>2. Thẻ Áo khoác gió DKat -> Xem chi tiết -> dòng Đen / M (Hết hàng tại DKat Quận 1) -> Đặt trước<br>3. Để trống Họ tên, nhập SĐT và địa chỉ như dữ liệu -> Gửi đặt trước |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders {"branchId":1,"customer":{"fullName":"","phone":"0912000001","address":"2 Lê Lợi, Quận 1"},"items":[{"variantId":8,"quantity":1}]} |
| **Kết quả mong đợi** | Form không gửi, dưới ô Họ tên hiện 'Vui lòng nhập họ tên.' API: 422, code INVALID_PREORDER, details[0].field = customer.fullName. Không tạo đơn. |
| **Chạy thử chuẩn bị 25/11** | Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: 422 INVALID_PREORDER [{'field': 'customer.fullName', 'reason': 'String should have at least 1 character'}] |

## TC-PN-02

**Thiếu SĐT hoặc SĐT sai định dạng bị từ chối** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Như TC-PN-01. |
| **Dữ liệu đầu vào (seed)** | Họ tên Khách B \| Lần 1: SĐT để trống \| Lần 2: SĐT 12345 \| Địa chỉ 2 Lê Lợi, Quận 1 |
| **Các bước (giao diện)** | 1. Form đặt trước Áo khoác gió Đen / M như TC-PN-01<br>2. Nhập Họ tên, để trống SĐT -> Gửi đặt trước<br>3. Nhập SĐT 12345 -> Gửi đặt trước |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders: customer không có phone; rồi phone = "12345" |
| **Kết quả mong đợi** | Cả 2 lần form không gửi, dưới ô SĐT hiện 'Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.' API: 422 INVALID_PREORDER, details[0].field = customer.phone (lần 2 kèm lý do 'Số điện thoại phải có 10–11 chữ số, bắt đầu bằng 0 hoặc dùng mã +84'). |
| **Chạy thử chuẩn bị 25/11** | Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: thiếu -> 422 {'field': 'customer.phone', 'reason': 'Field required'}; '12345' -> 422 customer.phone |

## TC-PN-03

**Thiếu địa chỉ bị từ chối; hàng còn thì không cho đặt trước** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Như TC-PN-01. |
| **Dữ liệu đầu vào (seed)** | Lần 1: Khách B, 0912000001, địa chỉ để trống, Đen / M \| Lần 2: Khách B, 0912000001, 2 Lê Lợi, sản phẩm Áo khoác gió Đen / L (còn 6) |
| **Các bước (giao diện)** | 1. Form đặt trước Đen / M, để trống Địa chỉ -> Gửi đặt trước<br>2. Trong hộp chi tiết Áo khoác gió DKat, xem dòng Đen / L |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders thiếu customer.address; rồi đủ thông tin nhưng items[0].variantId = 9 (Đen / L) |
| **Kết quả mong đợi** | Lần 1: dưới ô Địa chỉ hiện 'Vui lòng nhập địa chỉ.'; API 422, details[0].field = customer.address. Lần 2: dòng Đen / L ghi Còn hàng, KHÔNG có nút Đặt trước; API 409 VARIANT_IN_STOCK ('Hàng còn đủ; vui lòng mua trực tiếp tại cửa hàng'). Tổng số đơn đặt trước vẫn 1 (chỉ đơn của chị Lan). |
| **Chạy thử chuẩn bị 25/11** | Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: thiếu địa chỉ -> 422 customer.address; Đen / L còn 6 -> 409 VARIANT_IN_STOCK; số đơn vẫn 1 |

## TC-PN-04

**Đặt trước thành công không trừ kho** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | CHẠY LẠI python -m scripts.demo_reset trước TC này (các lần gửi lỗi ở TC-PN-01..03 cũng tính vào giới hạn 5 lần / 10 phút / IP). Server CẤU HÌNH A. |
| **Dữ liệu đầu vào (seed)** | Website, Áo khoác gió DKat Đen / M, chi nhánh DKat Quận 1, tạo 3 đơn theo thứ tự: B = Khách B, 0912000001, 2 Lê Lợi Quận 1, Số lượng 2 \| C = Khách C, 0912000002, email = EMAIL_TEST_TO của .env, 3 Lê Lợi Quận 1, Số lượng 1 \| D = Khách D, 0912000003, 4 Lê Lợi Quận 1, Số lượng 1 |
| **Các bước (giao diện)** | 1. Website: đặt trước lần lượt B, C, D như dữ liệu, ghi lại 3 mã đơn PD-...<br>2. owner01 -> Kho hàng (F5): dòng AK-GIO-DEN-M<br>3. Đặt trước: xem 4 dòng |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders?branchId=1; GET /api/v1/inventory?branchId=1 |
| **Kết quả mong đợi** | Mỗi lần hiện 'Đặt trước thành công' + mã đơn, trạng thái Chờ hàng về; B tạm tính 1.198.000 đ. Trang Đặt trước: Lan, B, C, D đều Chờ hàng. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 0 / 0 / 0 (đặt trước KHÔNG trừ, không giữ kho). |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: B WAITING_STOCK 1198000.00, C WAITING_STOCK, D WAITING_STOCK; tồn AK-GIO-DEN-M CN01 (thực/giữ/khả dụng) = (0, 0, 0) |

## TC-PN-05

**Nhập 2 chiếc -> phân bổ FIFO đúng thứ tự đặt** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-04, server CẤU HÌNH A. Đăng nhập owner01. |
| **Dữ liệu đầu vào (seed)** | Nhập kho: Áo khoác gió DKat Đen / M, số lượng 2, ghi chú Hàng về đợt 1 |
| **Các bước (giao diện)** | 1. Kho hàng -> Nhập kho: biến thể Áo khoác gió Đen / M, số lượng 2 -> Xác nhận<br>2. Kho hàng (F5): dòng AK-GIO-DEN-M<br>3. Đặt trước: trạng thái 4 đơn<br>4. API: allocatedQuantity của từng đơn<br>5. Dòng chị Lan -> Thông báo |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id} cho Lan, B, C, D -> items[0].allocatedQuantity |
| **Kết quả mong đợi** | Chị Lan (đặt trước nhất): Sẵn sàng, phân bổ 1/1. B: vẫn Chờ hàng, phân bổ 1/2 (nhận phần còn lại). C, D: Chờ hàng, 0/1. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 2 / 2 / 0. Lịch sử thông báo của Lan: Email · Lỗi · NOT_CONFIGURED (cấu hình A tắt email) nên Lan vẫn Sẵn sàng, chưa phải Đã thông báo. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: {'lan': 'READY 1/1', 'b': 'WAITING_STOCK 1/2', 'c': 'WAITING_STOCK 0/1', 'd': 'WAITING_STOCK 0/1'}; tồn (2, 2, 0); thông báo Lan [('EMAIL', 'FAILED', 'NOT_CONFIGURED', 0)] |

## TC-PN-06

**Đơn đủ hàng -> READY -> gửi SMS -> Đã thông báo** (Thông báo)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-05, server CẤU HÌNH A (SMS sandbox). |
| **Dữ liệu đầu vào (seed)** | Nhập kho thêm 1 chiếc Áo khoác gió Đen / M, ghi chú Hàng về đợt 2 |
| **Các bước (giao diện)** | 1. Kho hàng -> Nhập kho: Đen / M, số lượng 1 -> Xác nhận<br>2. Đặt trước: trạng thái B, C<br>3. Dòng B -> Thông báo<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id B}/notifications |
| **Kết quả mong đợi** | B: Đã thông báo, phân bổ 2/2. Lịch sử của B: SMS · 0912***001 · Đã gửi (sandbox, không có tin thật). C: vẫn Chờ hàng 0/1. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 3 / 3 / 0. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: B NOTIFIED 2/2, gửi [('SMS', 'SENT', '', 0)]; C WAITING_STOCK 0/1; tồn (3, 3, 0) |

## TC-PN-07

**SMS lỗi -> tự chuyển sang email** (Thông báo)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-06. ĐỔI SANG CẤU HÌNH B (sai khóa eSMS, email thật). Người test mở hộp thư EMAIL_TEST_TO. |
| **Dữ liệu đầu vào (seed)** | Nhập kho thêm 1 chiếc Áo khoác gió Đen / M, ghi chú Hàng về đợt 3 \| Khách C có SĐT 0912000002 và email EMAIL_TEST_TO |
| **Các bước (giao diện)** | 1. Kho hàng -> Nhập kho: Đen / M, số lượng 1 -> Xác nhận (chờ vài giây)<br>2. Đặt trước: dòng C -> Thông báo<br>3. Mở hộp thư EMAIL_TEST_TO<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id C}/notifications |
| **Kết quả mong đợi** | C: Đã thông báo, 1/1. Lịch sử của C: dòng 1 SMS · Lỗi · AUTH_FAILED; dòng 2 Email · Đã gửi. Hộp thư nhận email '[DKat] Hàng đã về - đơn PD-...: mời đến mua trước dd/mm' gồm 'Áo khoác gió DKat (SKU AK-GIO-DEN-M) x 1: 599.000đ', chi nhánh DKat Quận 1 (12 Lê Lợi...), hạn giữ hàng 7 ngày, 'Tổng tiền: 599.000đ (chưa thanh toán)'. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 4 / 4 / 0. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: C NOTIFIED 1/1, gửi [('SMS', 'FAILED', 'AUTH_FAILED', 0), ('EMAIL', 'SENT', '', 0)]; tồn (4, 4, 0) |

## TC-PN-08

**Thử lại tự động: email lỗi được gửi lại, không gửi trùng** (Thông báo)

| | |
|---|---|
| **Điều kiện** | Ngay sau TC-PN-07, server CẤU HÌNH B (job thử lại mỗi 30 giây). |
| **Dữ liệu đầu vào (seed)** | Thông báo lỗi có sẵn: Email của chị Lan (NOT_CONFIGURED từ TC-PN-05) và SMS của C (AUTH_FAILED, nhưng C đã nhận email) |
| **Các bước (giao diện)** | 1. Chờ 30-60 giây<br>2. Đặt trước: dòng chị Lan -> Thông báo<br>3. Dòng C -> Thông báo |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id Lan}/notifications và {id C} |
| **Kết quả mong đợi** | Lan: Email · Đã gửi · gửi lại 1 (hộp thư nhóm nhận email); trạng thái đơn Lan chuyển Đã thông báo. C: SMS vẫn Lỗi, KHÔNG được gửi lại (không có 'gửi lại') vì khách đã nhận qua email; không có email thứ 2 gửi cho C. Ghi chú: job chạy lần đầu 30 giây sau khi bật server, nên email của Lan có thể đã được gửi lại ngay trong lúc làm TC-PN-07. |
| **Chạy thử chuẩn bị 25/11** | Đạt (gọi job thử lại trực tiếp; trên server job chạy mỗi NOTIFY_RETRY_INTERVAL_SECONDS) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: lượt thử lại {'checked': 1, 'sent': 1, 'failed': 0, 'skipped': 0}; Lan NOTIFIED 1/1 [('EMAIL', 'SENT', '', 1)]; C [('SMS', 'FAILED', 'AUTH_FAILED', 0), ('EMAIL', 'SENT', '', 0)] |

## TC-PN-09

**Gửi lại thủ công bằng nút Gửi lại** (Thông báo)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-08, server CẤU HÌNH B. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Thông báo SMS lỗi của C (AUTH_FAILED) |
| **Các bước (giao diện)** | 1. staff01 -> Đặt trước: dòng C -> Thông báo<br>2. Dòng SMS (Lỗi) -> Gửi lại<br>3. Xem lại dòng SMS<br>4. (API) gửi lại dòng Email đã gửi của C |
| **Kiểm tra nhanh qua API** | POST /api/v1/notifications/{id SMS của C}/resend; POST /api/v1/notifications/{id Email của C}/resend |
| **Kết quả mong đợi** | Sau Gửi lại: dòng SMS vẫn Lỗi (AUTH_FAILED vì khóa sai), hiện 'gửi lại 1'. Dòng Email đã gửi không có nút Gửi lại; API gửi lại SMS -> 200, result FAILED, retryCount 1; gửi lại email đã SENT -> 409 NOTIFICATION_NOT_FAILED. |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: gửi lại SMS -> 200 FAILED retryCount 1 (AUTH_FAILED); gửi lại email đã SENT -> 409 NOTIFICATION_NOT_FAILED |

## TC-PN-10

**Xác nhận nhận hàng mới trừ kho** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-09. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Đơn B (2 chiếc, 1.198.000 đ, Đã thông báo) \| Thu tiền mặt đủ 1.198.000 đ |
| **Các bước (giao diện)** | 1. Kho hàng (F5): ghi 3 cột AK-GIO-DEN-M<br>2. Đặt trước: dòng B -> Ghi nhận tiền -> OK<br>3. Kho hàng (F5)<br>4. Đặt trước: dòng B -> Xác nhận giao -> OK<br>5. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders/{id B}/confirm-payment {"paymentMethod":"CASH","amount":"1198000"}; POST .../fulfill {} |
| **Kết quả mong đợi** | Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng): trước 4 / 4 / 0; sau Ghi nhận tiền vẫn 4 / 4 / 0 (thu tiền chưa trừ kho), thanh toán Đã thanh toán; sau Xác nhận giao: B Đã nhận hàng và tồn = 2 / 2 / 0 (trừ 2 chiếc khi giao). |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: trước (4, 4, 0); sau thu tiền PAID (4, 4, 0); sau giao FULFILLED (2, 2, 0) |

## TC-PN-11

**Hủy đơn đang giữ hàng -> giải phóng cho khách kế tiếp** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-10, server CẤU HÌNH B. Đăng nhập staff01:staff. |
| **Dữ liệu đầu vào (seed)** | Hủy đơn C (đang giữ 1 chiếc), lý do: Khách không lấy nữa \| Khách D đang chờ (0/1), chỉ có SĐT |
| **Các bước (giao diện)** | 1. Đặt trước: dòng C -> Hủy, nhập lý do -> OK<br>2. Xem trạng thái C và D<br>3. Dòng D -> Thông báo<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | POST /api/v1/preorders/{id C}/cancel {"reason":"Khách không lấy nữa"}; GET /api/v1/preorders/{id D} |
| **Kết quả mong đợi** | C: Đã hủy. Chiếc của C chuyển ngay cho D: D Sẵn sàng, phân bổ 1/1. Lịch sử của D: SMS · Lỗi · AUTH_FAILED (cấu hình B; D không có email nên D vẫn Sẵn sàng). Job thử lại chạy mỗi 30 giây nên dòng SMS có thể đã hiện 'gửi lại 1..3', sau lần thứ 3 ghi RETRY_EXHAUSTED và dừng. Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 2 / 2 / 0 (Lan 1 + D 1). |
| **Chạy thử chuẩn bị 25/11** | Đạt (script check_preorder_notify) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: C -> CANCELLED; D READY 1/1 gửi [('SMS', 'FAILED', 'AUTH_FAILED', 0)]; tồn (2, 2, 0) |

## TC-PN-12

**Hết hạn giữ hàng -> Hết hạn, giải phóng hàng** (Đặt trước)

| | |
|---|---|
| **Điều kiện** | Sau TC-PN-11. Job hết hạn chưa tự chạy trên server (BUG-006): chạy tay. Cần MySQL Workbench hoặc client SQL vào DB dkat_demo. |
| **Dữ liệu đầu vào (seed)** | Đơn chị Lan (Đã thông báo, giữ 1 chiếc, hạn giữ còn 7 ngày) \| Đưa hạn giữ về quá khứ |
| **Các bước (giao diện)** | 1. SQL: UPDATE preorders SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE customer_name = 'Trần Thị Lan';<br>2. backend/: .venv\Scripts\python.exe -m app.workers.preorder_expiry<br>3. Đặt trước (F5): dòng Lan, dòng D<br>4. Kho hàng (F5) |
| **Kiểm tra nhanh qua API** | GET /api/v1/preorders/{id Lan} |
| **Kết quả mong đợi** | Lệnh in 'Expired preorders: 1'. Lan: Hết hạn, phân bổ 0/1. D không đổi (Sẵn sàng 1/1). Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng) = 2 / 1 / 1 (chiếc của Lan được giải phóng, không còn ai chờ nên thành khả dụng để bán). |
| **Chạy thử chuẩn bị 25/11** | Đạt (gọi job hết hạn trực tiếp, như bước 2) |
| **Kết quả vòng 2 (25/11/2026)** | **Pass**: job hết hạn: 1 đơn; Lan EXPIRED 0/1; D READY 1/1; tồn (2, 1, 1) |

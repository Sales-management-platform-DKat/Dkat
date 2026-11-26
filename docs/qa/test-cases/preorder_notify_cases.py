"""Single source of the Pre-order & Notification integration test cases (round of Day 16).

Every expected value was measured on fresh seed data on 25/11/2026 with backend/scripts/check_preorder_notify.py
(12/12). "Tồn" is written (Tồn thực / Đã giữ / Khả dụng) as in the Kho hàng screen, branch DKat Quận 1.
"""

SHEET = "Đặt trước & Thông báo"
SLUG = "preorder-notify"
SUITE_LABEL = "preorder-notify"
TITLE = "Test case tích hợp Đặt trước & Thông báo (vòng kiểm thử Ngày 16)"
PASSWORD = "DKat@Demo2026"

PREPARE = [
    "Chuẩn bị chung (chạy đúng thứ tự TC-PN-01 -> 12 trên seed mới; các TC sau dùng đơn của TC trước):",
    "1. git checkout develop && git pull. backend/.env: DB_NAME=dkat_demo, DB_SSL_MODE=disabled (MySQL trên máy), DKAT_ADMIN_TOKEN >= 32 ký tự, "
    "SMTP_* (Gmail App Password) và EMAIL_TEST_TO = hộp thư của người test.",
    "2. backend/: python -m scripts.demo_reset (~20 giây). frontend/: .env.local có VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1, VITE_PUBLIC_STORE_ID=1; npm run dev.",
    "3. Bật server theo CẤU HÌNH A cho TC-PN-01..06 (PowerShell, trong backend/): "
    "$env:ESMS_SANDBOX='true'; $env:SMTP_HOST=''; $env:NOTIFY_RETRY_ENABLED='false'; .venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000   "
    "(SMS sandbox: eSMS kiểm tra yêu cầu nhưng KHÔNG gửi, không tốn tiền; email tắt).",
    "4. Trước TC-PN-07 đổi sang CẤU HÌNH B: Ctrl+C rồi trong CỬA SỔ POWERSHELL MỚI: "
    "$env:ESMS_API_KEY='SAI-KHOA-KIEM-THU'; $env:NOTIFY_RETRY_INTERVAL_SECONDS='30'; .venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000   "
    "(SMS luôn lỗi AUTH_FAILED, email thật qua SMTP, job thử lại chạy mỗi 30 giây). Không cần đăng nhập lại.",
    f"5. Tài khoản (mật khẩu {PASSWORD}): owner01 (cửa sổ thường, nhập kho) và staff01:staff (cửa sổ InPrivate, xử lý đơn). Website khách: http://127.0.0.1:5173/#/catalog.",
    "6. Đọc tồn: Kho hàng (F5), dòng AK-GIO-DEN-M, 3 cột Tồn thực / Đã giữ / Khả dụng. Lịch sử thông báo: Đặt trước -> dòng đơn -> nút Thông báo.",
    "7. Số lượng đã phân bổ cho từng đơn (ví dụ 1/2) không hiện trên giao diện: xem qua API GET /api/v1/preorders/{id} -> items[0].allocatedQuantity "
    "(Swagger http://127.0.0.1:8000/docs, Authorize bằng token owner01).",
    "8. Kiểm tra tự động toàn bộ: python -m scripts.demo_reset rồi python -m scripts.check_preorder_notify (không cần bật server; gửi 2 email thật).",
]

SEED = {
    "branches": "CN01 DKat Quận 1 (id 1), hotline 028 3822 1001",
    "stock_cn01": "Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, variantId 8, 599.000 đ): 0 / 0 / 0. Áo khoác gió DKat Đen / L (AK-GIO-DEN-L, variantId 9): còn 6. "
                  "Đơn có sẵn: Trần Thị Lan đặt 1 chiếc Đen / M lúc 18:00 hôm qua (xếp hàng số 1), chỉ có email (hộp thư nhóm), chưa thanh toán",
}

STOCK = "Tồn AK-GIO-DEN-M (Tồn thực / Đã giữ / Khả dụng)"

# id, chức năng, tiêu đề, điều kiện, dữ liệu đầu vào (seed), các bước (giao diện), kiểm tra API, kết quả mong đợi, nhãn
CASES = [
    ("TC-PN-01", "Đặt trước", "Thiếu họ tên bị từ chối",
     "Đã làm Chuẩn bị chung, server CẤU HÌNH A. Không cần đăng nhập.",
     "Sản phẩm: Áo khoác gió DKat Đen / M (hết hàng) | Họ tên: (để trống) | SĐT 0912000001 | Địa chỉ 2 Lê Lợi, Quận 1",
     "1. Mở http://127.0.0.1:5173/#/catalog, chi nhánh DKat Quận 1, ô tìm gõ khoác\n2. Thẻ Áo khoác gió DKat · Đen / M (Hết hàng) -> Đặt trước\n"
     "3. Để trống Họ tên, nhập SĐT và địa chỉ như dữ liệu -> Gửi đặt trước",
     "POST /api/v1/preorders {\"branchId\":1,\"customer\":{\"fullName\":\"\",\"phone\":\"0912000001\",\"address\":\"2 Lê Lợi, Quận 1\"},\"items\":[{\"variantId\":8,\"quantity\":1}]}",
     "Form không gửi, dưới ô Họ tên hiện 'Vui lòng nhập họ tên.' API: 422, code INVALID_PREORDER, details[0].field = customer.fullName. Không tạo đơn.",
     ["preorder"]),
    ("TC-PN-02", "Đặt trước", "Thiếu SĐT hoặc SĐT sai định dạng bị từ chối",
     "Như TC-PN-01.",
     "Họ tên Khách B | Lần 1: SĐT để trống | Lần 2: SĐT 12345 | Địa chỉ 2 Lê Lợi, Quận 1",
     "1. Form đặt trước Áo khoác gió Đen / M như TC-PN-01\n2. Nhập Họ tên, để trống SĐT -> Gửi đặt trước\n3. Nhập SĐT 12345 -> Gửi đặt trước",
     "POST /api/v1/preorders: customer không có phone; rồi phone = \"12345\"",
     "Cả 2 lần form không gửi, dưới ô SĐT hiện 'Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.' "
     "API: 422 INVALID_PREORDER, details[0].field = customer.phone (lần 2 kèm lý do 'Số điện thoại phải có 10–11 chữ số, bắt đầu bằng 0 hoặc dùng mã +84').",
     ["preorder"]),
    ("TC-PN-03", "Đặt trước", "Thiếu địa chỉ bị từ chối; hàng còn thì không cho đặt trước",
     "Như TC-PN-01.",
     "Lần 1: Khách B, 0912000001, địa chỉ để trống, Đen / M | Lần 2: Khách B, 0912000001, 2 Lê Lợi, sản phẩm Áo khoác gió Đen / L (còn 6)",
     "1. Form đặt trước Đen / M, để trống Địa chỉ -> Gửi đặt trước\n2. Trên danh mục, xem thẻ Áo khoác gió DKat · Đen / L",
     "POST /api/v1/preorders thiếu customer.address; rồi đủ thông tin nhưng items[0].variantId = 9 (Đen / L)",
     "Lần 1: dưới ô Địa chỉ hiện 'Vui lòng nhập địa chỉ.'; API 422, details[0].field = customer.address. "
     "Lần 2: thẻ Đen / L ghi Còn hàng, KHÔNG có nút Đặt trước; API 409 VARIANT_IN_STOCK ('Hàng còn đủ; vui lòng mua trực tiếp tại cửa hàng'). Tổng số đơn đặt trước vẫn 1 (chỉ đơn của chị Lan).",
     ["preorder"]),
    ("TC-PN-04", "Đặt trước", "Đặt trước thành công không trừ kho",
     "CHẠY LẠI python -m scripts.demo_reset trước TC này (các lần gửi lỗi ở TC-PN-01..03 cũng tính vào giới hạn 5 lần / 10 phút / IP). Server CẤU HÌNH A.",
     "Website, Áo khoác gió DKat Đen / M, chi nhánh DKat Quận 1, tạo 3 đơn theo thứ tự: "
     "B = Khách B, 0912000001, 2 Lê Lợi Quận 1, Số lượng 2 | C = Khách C, 0912000002, email = EMAIL_TEST_TO của .env, 3 Lê Lợi Quận 1, Số lượng 1 | "
     "D = Khách D, 0912000003, 4 Lê Lợi Quận 1, Số lượng 1",
     "1. Website: đặt trước lần lượt B, C, D như dữ liệu, ghi lại 3 mã đơn PD-...\n2. owner01 -> Kho hàng (F5): dòng AK-GIO-DEN-M\n3. Đặt trước: xem 4 dòng",
     "GET /api/v1/preorders?branchId=1; GET /api/v1/inventory?branchId=1",
     "Mỗi lần hiện 'Đặt trước thành công' + mã đơn, trạng thái Chờ hàng về; B tạm tính 1.198.000 đ. "
     f"Trang Đặt trước: Lan, B, C, D đều Chờ hàng. {STOCK} = 0 / 0 / 0 (đặt trước KHÔNG trừ, không giữ kho).",
     ["preorder", "inventory"]),
    ("TC-PN-05", "Đặt trước", "Nhập 2 chiếc -> phân bổ FIFO đúng thứ tự đặt",
     "Sau TC-PN-04, server CẤU HÌNH A. Đăng nhập owner01.",
     "Nhập kho: Áo khoác gió DKat Đen / M, số lượng 2, ghi chú Hàng về đợt 1",
     "1. Kho hàng -> Nhập kho: biến thể Áo khoác gió Đen / M, số lượng 2 -> Xác nhận\n2. Kho hàng (F5): dòng AK-GIO-DEN-M\n"
     "3. Đặt trước: trạng thái 4 đơn\n4. API: allocatedQuantity của từng đơn\n5. Dòng chị Lan -> Thông báo",
     "GET /api/v1/preorders/{id} cho Lan, B, C, D -> items[0].allocatedQuantity",
     "Chị Lan (đặt trước nhất): Sẵn sàng, phân bổ 1/1. B: vẫn Chờ hàng, phân bổ 1/2 (nhận phần còn lại). C, D: Chờ hàng, 0/1. "
     f"{STOCK} = 2 / 2 / 0. Lịch sử thông báo của Lan: Email · Lỗi · NOT_CONFIGURED (cấu hình A tắt email) nên Lan vẫn Sẵn sàng, chưa phải Đã thông báo.",
     ["preorder", "inventory", "fifo"]),
    ("TC-PN-06", "Thông báo", "Đơn đủ hàng -> READY -> gửi SMS -> Đã thông báo",
     "Sau TC-PN-05, server CẤU HÌNH A (SMS sandbox).",
     "Nhập kho thêm 1 chiếc Áo khoác gió Đen / M, ghi chú Hàng về đợt 2",
     "1. Kho hàng -> Nhập kho: Đen / M, số lượng 1 -> Xác nhận\n2. Đặt trước: trạng thái B, C\n3. Dòng B -> Thông báo\n4. Kho hàng (F5)",
     "GET /api/v1/preorders/{id B}/notifications",
     "B: Đã thông báo, phân bổ 2/2. Lịch sử của B: SMS · 0912***001 · Đã gửi (sandbox, không có tin thật). C: vẫn Chờ hàng 0/1. "
     f"{STOCK} = 3 / 3 / 0.",
     ["notification", "preorder"]),
    ("TC-PN-07", "Thông báo", "SMS lỗi -> tự chuyển sang email",
     "Sau TC-PN-06. ĐỔI SANG CẤU HÌNH B (sai khóa eSMS, email thật). Người test mở hộp thư EMAIL_TEST_TO.",
     "Nhập kho thêm 1 chiếc Áo khoác gió Đen / M, ghi chú Hàng về đợt 3 | Khách C có SĐT 0912000002 và email EMAIL_TEST_TO",
     "1. Kho hàng -> Nhập kho: Đen / M, số lượng 1 -> Xác nhận (chờ vài giây)\n2. Đặt trước: dòng C -> Thông báo\n3. Mở hộp thư EMAIL_TEST_TO\n4. Kho hàng (F5)",
     "GET /api/v1/preorders/{id C}/notifications",
     "C: Đã thông báo, 1/1. Lịch sử của C: dòng 1 SMS · Lỗi · AUTH_FAILED; dòng 2 Email · Đã gửi. Hộp thư nhận email "
     "'[DKat] Hàng đã về - đơn PD-...: mời đến mua trước dd/mm' gồm 'Áo khoác gió DKat (SKU AK-GIO-DEN-M) x 1: 599.000đ', chi nhánh DKat Quận 1 (12 Lê Lợi...), hạn giữ hàng 7 ngày, 'Tổng tiền: 599.000đ (chưa thanh toán)'. "
     f"{STOCK} = 4 / 4 / 0.",
     ["notification"]),
    ("TC-PN-08", "Thông báo", "Thử lại tự động: email lỗi được gửi lại, không gửi trùng",
     "Ngay sau TC-PN-07, server CẤU HÌNH B (job thử lại mỗi 30 giây).",
     "Thông báo lỗi có sẵn: Email của chị Lan (NOT_CONFIGURED từ TC-PN-05) và SMS của C (AUTH_FAILED, nhưng C đã nhận email)",
     "1. Chờ 30-60 giây\n2. Đặt trước: dòng chị Lan -> Thông báo\n3. Dòng C -> Thông báo",
     "GET /api/v1/preorders/{id Lan}/notifications và {id C}",
     "Lan: Email · Đã gửi · gửi lại 1 (hộp thư nhóm nhận email); trạng thái đơn Lan chuyển Đã thông báo. "
     "C: SMS vẫn Lỗi, KHÔNG được gửi lại (không có 'gửi lại') vì khách đã nhận qua email; không có email thứ 2 gửi cho C. Ghi chú: job chạy lần đầu 30 giây sau khi bật server, nên email của Lan có thể đã được gửi lại ngay trong lúc làm TC-PN-07.",
     ["notification", "retry"]),
    ("TC-PN-09", "Thông báo", "Gửi lại thủ công bằng nút Gửi lại",
     "Sau TC-PN-08, server CẤU HÌNH B. Đăng nhập staff01:staff.",
     "Thông báo SMS lỗi của C (AUTH_FAILED)",
     "1. staff01 -> Đặt trước: dòng C -> Thông báo\n2. Dòng SMS (Lỗi) -> Gửi lại\n3. Xem lại dòng SMS\n4. (API) gửi lại dòng Email đã gửi của C",
     "POST /api/v1/notifications/{id SMS của C}/resend; POST /api/v1/notifications/{id Email của C}/resend",
     "Sau Gửi lại: dòng SMS vẫn Lỗi (AUTH_FAILED vì khóa sai), hiện 'gửi lại 1'. Dòng Email đã gửi không có nút Gửi lại; "
     "API gửi lại SMS -> 200, result FAILED, retryCount 1; gửi lại email đã SENT -> 409 NOTIFICATION_NOT_FAILED.",
     ["notification", "retry"]),
    ("TC-PN-10", "Đặt trước", "Xác nhận nhận hàng mới trừ kho",
     "Sau TC-PN-09. Đăng nhập staff01:staff.",
     "Đơn B (2 chiếc, 1.198.000 đ, Đã thông báo) | Thu tiền mặt đủ 1.198.000 đ",
     "1. Kho hàng (F5): ghi 3 cột AK-GIO-DEN-M\n2. Đặt trước: dòng B -> Ghi nhận tiền -> OK\n3. Kho hàng (F5)\n4. Đặt trước: dòng B -> Xác nhận giao -> OK\n5. Kho hàng (F5)",
     "POST /api/v1/preorders/{id B}/confirm-payment {\"paymentMethod\":\"CASH\",\"amount\":\"1198000\"}; POST .../fulfill {}",
     f"{STOCK}: trước 4 / 4 / 0; sau Ghi nhận tiền vẫn 4 / 4 / 0 (thu tiền chưa trừ kho), thanh toán Đã thanh toán; "
     "sau Xác nhận giao: B Đã nhận hàng và tồn = 2 / 2 / 0 (trừ 2 chiếc khi giao).",
     ["preorder", "inventory"]),
    ("TC-PN-11", "Đặt trước", "Hủy đơn đang giữ hàng -> giải phóng cho khách kế tiếp",
     "Sau TC-PN-10, server CẤU HÌNH B. Đăng nhập staff01:staff.",
     "Hủy đơn C (đang giữ 1 chiếc), lý do: Khách không lấy nữa | Khách D đang chờ (0/1), chỉ có SĐT",
     "1. Đặt trước: dòng C -> Hủy, nhập lý do -> OK\n2. Xem trạng thái C và D\n3. Dòng D -> Thông báo\n4. Kho hàng (F5)",
     "POST /api/v1/preorders/{id C}/cancel {\"reason\":\"Khách không lấy nữa\"}; GET /api/v1/preorders/{id D}",
     "C: Đã hủy. Chiếc của C chuyển ngay cho D: D Sẵn sàng, phân bổ 1/1. Lịch sử của D: SMS · Lỗi · AUTH_FAILED (cấu hình B; D không có email nên D vẫn Sẵn sàng). Job thử lại chạy mỗi 30 giây nên dòng SMS có thể đã hiện 'gửi lại 1..3', sau lần thứ 3 "
     f"ghi RETRY_EXHAUSTED và dừng. {STOCK} = 2 / 2 / 0 (Lan 1 + D 1).",
     ["preorder", "inventory", "fifo"]),
    ("TC-PN-12", "Đặt trước", "Hết hạn giữ hàng -> Hết hạn, giải phóng hàng",
     "Sau TC-PN-11. Job hết hạn chưa tự chạy trên server (BUG-006): chạy tay. Cần MySQL Workbench hoặc client SQL vào DB dkat_demo.",
     "Đơn chị Lan (Đã thông báo, giữ 1 chiếc, hạn giữ còn 7 ngày) | Đưa hạn giữ về quá khứ",
     "1. SQL: UPDATE preorders SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 MINUTE WHERE customer_name = 'Trần Thị Lan';\n"
     "2. backend/: .venv\\Scripts\\python.exe -m app.workers.preorder_expiry\n3. Đặt trước (F5): dòng Lan, dòng D\n4. Kho hàng (F5)",
     "GET /api/v1/preorders/{id Lan}",
     "Lệnh in 'Expired preorders: 1'. Lan: Hết hạn, phân bổ 0/1. D không đổi (Sẵn sàng 1/1). "
     f"{STOCK} = 2 / 1 / 1 (chiếc của Lan được giải phóng, không còn ai chờ nên thành khả dụng để bán).",
     ["preorder", "inventory"]),
]

TRIAL = {c[0]: "Đạt (script check_preorder_notify)" for c in CASES}
TRIAL.update({
    "TC-PN-01": "Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx",
    "TC-PN-02": "Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx",
    "TC-PN-03": "Đạt (API); thông báo trên form: đúng theo code LiveCatalog.jsx",
    "TC-PN-08": "Đạt (gọi job thử lại trực tiếp; trên server job chạy mỗi NOTIFY_RETRY_INTERVAL_SECONDS)",
    "TC-PN-12": "Đạt (gọi job hết hạn trực tiếp, như bước 2)",
})

# Round 2 (25/11/2026), measured on fresh demo_reset data; log docs/qa/test-runs/2026-11-25-round2/logs/r2_50_preorder_notify.log
RESULTS_DATE = "25/11/2026"
RESULTS_TESTER = "Tuấn"
RESULTS = {
    'TC-PN-01': ('Pass', "422 INVALID_PREORDER [{'field': 'customer.fullName', 'reason': 'String should have at least 1 character'}]"),
    'TC-PN-02': ('Pass', "thiếu -> 422 {'field': 'customer.phone', 'reason': 'Field required'}; '12345' -> 422 customer.phone"),
    'TC-PN-03': ('Pass', 'thiếu địa chỉ -> 422 customer.address; Đen / L còn 6 -> 409 VARIANT_IN_STOCK; số đơn vẫn 1'),
    'TC-PN-04': ('Pass', 'B WAITING_STOCK 1198000.00, C WAITING_STOCK, D WAITING_STOCK; tồn AK-GIO-DEN-M CN01 (thực/giữ/khả dụng) = (0, 0, 0)'),
    'TC-PN-05': ('Pass', "{'lan': 'READY 1/1', 'b': 'WAITING_STOCK 1/2', 'c': 'WAITING_STOCK 0/1', 'd': 'WAITING_STOCK 0/1'}; tồn (2, 2, 0); thông báo Lan [('EMAIL', 'FAILED', 'NOT_CONFIGURED', 0)]"),
    'TC-PN-06': ('Pass', "B NOTIFIED 2/2, gửi [('SMS', 'SENT', '', 0)]; C WAITING_STOCK 0/1; tồn (3, 3, 0)"),
    'TC-PN-07': ('Pass', "C NOTIFIED 1/1, gửi [('SMS', 'FAILED', 'AUTH_FAILED', 0), ('EMAIL', 'SENT', '', 0)]; tồn (4, 4, 0)"),
    'TC-PN-08': ('Pass', "lượt thử lại {'checked': 1, 'sent': 1, 'failed': 0, 'skipped': 0}; Lan NOTIFIED 1/1 [('EMAIL', 'SENT', '', 1)]; C [('SMS', 'FAILED', 'AUTH_FAILED', 0), ('EMAIL', 'SENT', '', 0)]"),
    'TC-PN-09': ('Pass', 'gửi lại SMS -> 200 FAILED retryCount 1 (AUTH_FAILED); gửi lại email đã SENT -> 409 NOTIFICATION_NOT_FAILED'),
    'TC-PN-10': ('Pass', 'trước (4, 4, 0); sau thu tiền PAID (4, 4, 0); sau giao FULFILLED (2, 2, 0)'),
    'TC-PN-11': ('Pass', "C -> CANCELLED; D READY 1/1 gửi [('SMS', 'FAILED', 'AUTH_FAILED', 0)]; tồn (2, 2, 0)"),
    'TC-PN-12': ('Pass', 'job hết hạn: 1 đơn; Lan EXPIRED 0/1; D READY 1/1; tồn (2, 1, 1)'),
}

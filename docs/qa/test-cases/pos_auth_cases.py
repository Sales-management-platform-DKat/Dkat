"""Single source of the POS & Auth integration test cases (round of Day 16).

Used by build_pos_auth.py to produce: the "POS & Auth" sheet of docs/qa/DKat_Test_Cases.xlsx,
docs/qa/test-cases/pos-auth.md and one GitHub issue body per test case.
Every expected value was checked on fresh seed data on 25/11/2026 (API: backend/scripts/check_pos_auth.py
12/12, UI: Edge).
"""

PASSWORD = "DKat@Demo2026"
URL = "http://127.0.0.1:5173"

PREPARE = [
    "Chuẩn bị chung (làm 1 lần trước khi chạy TC-PA-01; chạy lại nếu dữ liệu đã bị dùng):",
    "1. git checkout develop && git pull. backend/.env có DB_NAME=dkat_demo (và DB_SSL_MODE=disabled với MySQL cài trên máy), DKAT_ADMIN_TOKEN >= 32 ký tự.",
    "2. Trong backend/: python -m scripts.demo_reset (~20 giây) rồi python -m uvicorn app.main:app --port 8000.",
    "3. Trong frontend/: .env.local có VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1, VITE_PUBLIC_STORE_ID=1; chạy npm run dev, mở http://127.0.0.1:5173/#/login.",
    f"4. Mật khẩu mọi tài khoản: {PASSWORD}. Tên đăng nhập: owner01 | manager01:manager | staff01:staff (nhân viên PHẢI có hậu tố :staff / :manager).",
    "5. Mỗi tài khoản một cửa sổ riêng (OWNER cửa sổ thường, nhân viên cửa sổ InPrivate/Ẩn danh): đăng nhập 2 tài khoản trong cùng cửa sổ sẽ đè phiên của nhau.",
    "6. Chạy theo thứ tự TC-PA-01 -> 12 (TC-PA-06, 10 dùng đơn tạo ở TC-PA-05). Trước khi đọc tồn kho: mở menu Kho hàng rồi nhấn F5.",
    "7. Kiểm tra tự động cùng dữ liệu: python -m scripts.check_pos_auth (sau demo_reset, server đang chạy) in PASS/FAIL 12 test case.",
]

SEED = {
    "branches": "CN01 DKat Quận 1 (id 1), CN02 DKat Cầu Giấy (id 2), CN03 DKat Hải Châu (id 3)",
    "stock_cn01": "Áo thun cotton DKat Trắng / M (AT-COT-M, 199.000 đ) tồn 11; Mũ lưỡi trai DKat Đen (MU-LT-DEN, 149.000 đ) tồn 10; "
                  "Quần jean slim Xanh / 29 (QJ-SLIM-29, 449.000 đ) tồn 11; Xanh / 30 (QJ-SLIM-30) tồn 10; Xanh / 31 (QJ-SLIM-31) tồn 10; "
                  "Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, 599.000 đ) tồn 0",
}

# id, chức năng, tiêu đề, điều kiện, dữ liệu đầu vào (seed), các bước (giao diện), kiểm tra API, kết quả mong đợi, nhãn
CASES = [
    ("TC-PA-01", "Xác thực", "Đăng nhập OWNER",
     "Đã làm Chuẩn bị chung. Chưa đăng nhập.",
     f"Tên đăng nhập: owner01 | Mật khẩu: {PASSWORD}",
     "1. Mở http://127.0.0.1:5173/#/login\n2. Nhập owner01 / mật khẩu\n3. Bấm Đăng nhập\n4. Xem menu bên trái và ô chọn chi nhánh ở góc trên",
     "POST /api/v1/auth/login {\"username\":\"owner01\",\"password\":\"" + PASSWORD + "\"}",
     "Vào trang Tổng quan (#/admin/dashboard). Menu đủ 12 mục: Tổng quan, Sản phẩm, Kho hàng, Bán hàng POS, Đơn bán, Đặt trước, Khách hàng, "
     "Nhân viên, Báo cáo, Chi nhánh, Thông báo, Cài đặt. Ô chi nhánh có 3 lựa chọn: DKat Quận 1, DKat Cầu Giấy, DKat Hải Châu. API: 200, user.role = owner.",
     ["auth"]),
    ("TC-PA-02", "Xác thực", "Đăng nhập MANAGER chỉ thấy chi nhánh được phân công",
     "Đã làm Chuẩn bị chung. Dùng cửa sổ InPrivate.",
     f"Tên đăng nhập: manager01:manager | Mật khẩu: {PASSWORD} | manager01 được phân công CN01 + CN02",
     "1. Mở #/login trong cửa sổ InPrivate\n2. Nhập manager01:manager / mật khẩu, bấm Đăng nhập\n3. Xem menu và ô chọn chi nhánh",
     "GET /api/v1/inventory?branchId=2 (token manager01) và ?branchId=3",
     "Vào Tổng quan. Menu 10 mục (KHÔNG có Chi nhánh, Cài đặt). Ô chi nhánh chỉ có DKat Quận 1, DKat Cầu Giấy. "
     "API: login 200 role = manager; tồn kho CN02 -> 200; CN03 -> 403.",
     ["auth", "rbac"]),
    ("TC-PA-03", "Xác thực", "Đăng nhập EMPLOYEE chỉ có màn hình bán hàng",
     "Đã làm Chuẩn bị chung. Dùng cửa sổ InPrivate (đăng xuất manager01 nếu đang mở).",
     f"Tên đăng nhập: staff01:staff | Mật khẩu: {PASSWORD} | staff01 thuộc CN01",
     "1. Đăng nhập staff01:staff\n2. Xem trang mở ra đầu tiên, menu, ô chi nhánh\n3. Gõ thẳng địa chỉ http://127.0.0.1:5173/#/admin/reports",
     "GET /api/v1/reports/summary?branchId=1 (token staff01)",
     "Mở thẳng Bán hàng POS. Menu 7 mục: Sản phẩm, Kho hàng, Bán hàng POS, Đơn bán, Đặt trước, Khách hàng, Thông báo (KHÔNG có Tổng quan, Báo cáo). "
     "Ô chi nhánh chỉ có DKat Quận 1. Mở #/admin/reports: thông báo vai trò này không có màn hình được yêu cầu. API báo cáo -> 403.",
     ["auth", "rbac"]),
    ("TC-PA-04", "Xác thực", "Đăng nhập sai bị từ chối",
     "Đã làm Chuẩn bị chung. Chưa đăng nhập.",
     f"Lần 1: staff01 (thiếu :staff) / {PASSWORD} | Lần 2: owner01 / SaiMatKhau@2026",
     "1. Nhập staff01 / mật khẩu đúng, bấm Đăng nhập\n2. Nhập owner01 / SaiMatKhau@2026, bấm Đăng nhập",
     "POST /api/v1/auth/login với 2 bộ dữ liệu trên; GET /api/v1/auth/me không gửi token",
     "Cả 2 lần ở lại trang đăng nhập, hộp báo 'Không thể hoàn tất - Tên đăng nhập hoặc mật khẩu không chính xác, hoặc tài khoản đã hết hạn.' "
     "API: 401, không có access_token; /auth/me không token -> 401.",
     ["auth"]),
    ("TC-PA-05", "POS / Đơn bán", "Tạo đơn POS chờ thanh toán",
     "Đăng nhập staff01:staff (TC-PA-03), chi nhánh DKat Quận 1. Tồn kho đúng seed.",
     "Sản phẩm: Áo thun cotton DKat Trắng / M (AT-COT-M) x2 + Mũ lưỡi trai DKat Đen (MU-LT-DEN) x1 | Khách: gõ 0901000001 -> Nguyễn Minh Anh | Chiết khấu 0",
     "1. Bán hàng POS: bấm ô Áo thun cotton DKat Trắng / M 2 lần, ô Mũ lưỡi trai DKat 1 lần\n2. Ô Tìm khách hàng gõ 0901000001, chọn Nguyễn Minh Anh\n"
     "3. Bấm Tạo đơn chờ thanh toán\n4. Hộp Xác nhận thanh toán: bấm Để xử lý sau\n5. Menu Đơn bán: tìm dòng 547.000 đ\n6. Kho hàng (F5): xem dòng AT-COT-M",
     "POST /api/v1/sales-orders {\"branchId\":1,\"customerId\":1,\"items\":[{\"variantId\":2,\"quantity\":2},{\"variantId\":7,\"quantity\":1}]}",
     "Hộp thanh toán hiện Khách cần thanh toán 547.000 đ (2 x 199.000 + 149.000). Sau Để xử lý sau: thông báo 'Đơn bán đã được tạo ở trạng thái chờ thanh toán.' "
     "Đơn bán: dòng mã DK-..., khách Nguyễn Minh Anh, 547.000 đ, Chờ thanh toán. Tồn AT-COT-M vẫn 11 (đơn chờ thanh toán chưa trừ kho). API: 201, status PENDING, totalAmount 547000.00.",
     ["pos"]),
    ("TC-PA-06", "POS / Đơn bán", "Xác nhận thanh toán tiền mặt trừ kho đúng",
     "Có đơn 547.000 đ Chờ thanh toán từ TC-PA-05. Đăng nhập staff01:staff.",
     "Đơn 547.000 đ của TC-PA-05 | Phương thức: tiền mặt, số tiền 547.000 đ",
     "1. Đơn bán: dòng 547.000 đ Chờ thanh toán -> Chi tiết\n2. Bấm Xác nhận đã nhận tiền mặt\n3. Đóng hộp, xem trạng thái dòng\n4. Kho hàng (F5): xem AT-COT-M và MU-LT-DEN",
     "POST /api/v1/sales-orders/{id}/confirm-payment {\"paymentMethod\":\"CASH\",\"amount\":\"547000\"}",
     "Đơn chuyển Đã thanh toán; chi tiết ghi Thanh toán: CASH · SUCCESS · 547.000 đ. Tồn CN01: AT-COT-M 11 -> 9, MU-LT-DEN 10 -> 9. "
     "API: 200, status PAID.",
     ["pos", "inventory"]),
    ("TC-PA-07", "POS / Đơn bán", "Xác nhận thanh toán sai số tiền bị từ chối (chỉ qua API)",
     "Đăng nhập staff01:staff. Giao diện luôn gửi đúng tổng tiền nên chỉ kiểm tra được qua API (Swagger http://127.0.0.1:8000/docs, Authorize bằng token staff01).",
     "Tạo đơn Quần jean slim Xanh / 31 (QJ-SLIM-31, variantId 6) x1 = 449.000 đ | Trả sai: 400.000",
     "1. POST /api/v1/sales-orders {\"branchId\":1,\"items\":[{\"variantId\":6,\"quantity\":1}]} -> ghi salesOrderId\n"
     "2. POST /api/v1/sales-orders/{salesOrderId}/confirm-payment {\"paymentMethod\":\"CASH\",\"amount\":\"400000\"}\n"
     "3. GET /api/v1/sales-orders/{salesOrderId}\n4. Dọn dữ liệu: POST .../cancel {\"reason\":\"Dọn dữ liệu\"}",
     "Như các bước",
     "Bước 2: 422, detail.code = PAYMENT_AMOUNT_MISMATCH, expectedAmount = 449000.00. Bước 3: đơn vẫn PENDING. Tồn QJ-SLIM-31 vẫn 10.",
     ["pos"]),
    ("TC-PA-08", "POS / Đơn bán", "Không bán vượt tồn khả dụng",
     "Đăng nhập staff01:staff, POS chi nhánh DKat Quận 1, giỏ hàng trống.",
     "Quần jean slim Xanh / 30 (QJ-SLIM-30, tồn 10) x11 | Áo khoác gió DKat Đen / M (AK-GIO-DEN-M, tồn 0)",
     "1. Bán hàng POS: bấm ô Quần jean slim Xanh / 30 liên tục 11 lần\n2. Xem số lượng trong giỏ và thông báo\n3. Thử bấm ô Áo khoác gió DKat Đen / M\n4. Bấm Xóa giỏ hàng",
     "POST /api/v1/sales-orders {\"branchId\":1,\"items\":[{\"variantId\":5,\"quantity\":11}]} và {\"variantId\":8,\"quantity\":1}",
     "Giỏ dừng ở 10, hiện 'Số lượng vượt quá tồn khả dụng.' Ô Áo khoác Đen / M mờ (Khả dụng: 0), không bấm được. "
     "API: 409, detail.code = OUT_OF_STOCK, items[].available = 10 (QJ-SLIM-30) và 0 (AK-GIO-DEN-M); không tạo đơn, tồn không đổi.",
     ["pos", "inventory"]),
    ("TC-PA-09", "POS / Đơn bán", "Hủy đơn PENDING",
     "Đăng nhập staff01:staff, giỏ hàng trống.",
     "Quần jean slim Xanh / 29 (QJ-SLIM-29, tồn 11) x1 = 449.000 đ | Lý do hủy: Khách đổi ý",
     "1. POS: bấm Quần jean slim Xanh / 29 một lần -> Tạo đơn chờ thanh toán -> Để xử lý sau\n2. Đơn bán: dòng 449.000 đ Chờ thanh toán (mới nhất) -> Chi tiết\n"
     "3. Bấm Hủy đơn, nhập lý do 'Khách đổi ý', OK\n4. Kho hàng (F5): xem QJ-SLIM-29",
     "POST /api/v1/sales-orders/{id}/cancel {\"reason\":\"Khách đổi ý\"}, rồi thử POST .../confirm-payment",
     "Hộp chi tiết chuyển 'DKat Quận 1 · Đã hủy', không còn nút thu tiền; dòng trong Đơn bán: Đã hủy. Tồn QJ-SLIM-29 vẫn 11. "
     "API: hủy 200 status CANCELLED, cancelReason 'Khách đổi ý'; thu tiền đơn đã hủy -> 409.",
     ["pos"]),
    ("TC-PA-10", "POS / Đơn bán", "OWNER hoàn đơn đã thanh toán và hoàn kho",
     "Đơn 547.000 đ Đã thanh toán từ TC-PA-06. Đăng nhập owner01 (cửa sổ thường).",
     "Đơn 547.000 đ của TC-PA-06 | Lý do: Khách trả hàng",
     "1. owner01 -> Đơn bán: dòng 547.000 đ Đã thanh toán (khách Nguyễn Minh Anh) -> Chi tiết\n2. Bấm Hoàn tiền, nhập 'Khách trả hàng', OK\n"
     "3. Đóng hộp, xem trạng thái dòng; mở lại Chi tiết\n4. Kho hàng (F5): xem AT-COT-M và MU-LT-DEN",
     "POST /api/v1/sales-orders/{id}/refund {\"reason\":\"Khách trả hàng\"}; gọi lại lần 2",
     "Dòng chuyển Đã hủy; chi tiết ghi khoản thanh toán CASH · REFUNDED · 547.000 đ. Tồn CN01 hoàn lại: AT-COT-M 9 -> 11, MU-LT-DEN 9 -> 10. "
     "API: 200, status CANCELLED, payments[].status = REFUNDED; hoàn lần 2 -> 409.",
     ["pos", "inventory"]),
    ("TC-PA-11", "Phân quyền", "EMPLOYEE không hoàn được đơn đã thanh toán",
     "Đăng nhập staff01:staff. Có ít nhất 1 đơn Đã thanh toán ở CN01 (dữ liệu seed có sẵn 53 đơn).",
     "Bất kỳ đơn Đã thanh toán nào ở DKat Quận 1, ví dụ dòng đầu danh sách Đơn bán",
     "1. staff01 -> Đơn bán: dòng Đã thanh toán đầu tiên -> Chi tiết\n2. Tìm nút Hoàn tiền",
     "POST /api/v1/sales-orders/{id}/refund {\"reason\":\"Thử\"} bằng token staff01",
     "Hộp chi tiết KHÔNG có nút Hoàn tiền (chỉ có ×). API: 403 'Bạn không có quyền thực hiện thao tác này.', đơn vẫn PAID.",
     ["pos", "rbac"]),
    ("TC-PA-12", "Phân quyền", "Phân quyền theo chi nhánh khi bán hàng",
     "Có token của staff01:staff và manager01:manager (Swagger, Authorize lần lượt từng token).",
     "Áo thun cotton DKat Trắng / L (AT-COT-L, variantId 3) x1 | staff01: CN02 (id 2) | manager01: CN03 (id 3) và CN02 (id 2)",
     "1. (staff01) POST /api/v1/sales-orders {\"branchId\":2,\"items\":[{\"variantId\":3,\"quantity\":1}]}\n2. (staff01) GET /api/v1/sales-orders?branchId=2\n"
     "3. (manager01) POST /api/v1/sales-orders với branchId 3\n4. (manager01) POST với branchId 2, rồi hủy đơn vừa tạo\n"
     "5. Giao diện: manager01 đổi ô chi nhánh sang DKat Cầu Giấy, mở Bán hàng POS",
     "Như các bước",
     "Bước 1, 2, 3: 403 'Bạn không có quyền truy cập chi nhánh này.' Bước 4: 201 (manager01 được bán ở CN02). "
     "Bước 5: POS hiện tồn của DKat Cầu Giấy (ví dụ Áo thun Trắng / L Khả dụng: 10).",
     ["pos", "rbac"]),
]

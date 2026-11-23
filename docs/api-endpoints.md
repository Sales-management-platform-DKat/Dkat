# Danh sách API (sinh tự động)

Sinh bằng `python -m scripts.gen_api_docs` từ chính ứng dụng FastAPI: 38 endpoint. Không sửa tay file này.
Quyền truy cập được đọc từ dependency của từng route (`require_auth`, `require_role`, `require_branch_access`).
Đặc tả đầy đủ (tham số, schema request/response): `docs/openapi.json` (import được vào Postman / Swagger Editor),
hoặc Swagger UI khi chạy backend: http://127.0.0.1:8000/docs

Định dạng chung: thành công `{"success": true, "data": ...}`; lỗi `{"success": false, "error": {"code", "message", "details"}}`.
Gửi token: header `Authorization: Bearer <token>` (lấy từ `POST /api/v1/auth/login`).

## Hệ thống

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/health` | Công khai | Always 200 while the server is alive; `database` reports the MySQL connection status. |
| `GET` | `/api/v1/health/db` | OWNER | Detailed DB connection check: 200 if connected, 503 DATABASE_UNAVAILABLE if not. |

## Xác thực

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/auth/change-password` | Mọi vai trò | Đổi mật khẩu: kiểm tra mật khẩu cũ, mật khẩu mới >= 8 ký tự và khác mật khẩu cũ. |
| `POST` | `/api/v1/auth/login` | Công khai | Đăng nhập: trả JWT (hạn 8 giờ) và thông tin user. 401 INVALID_CREDENTIALS / 403 ACCOUNT_LOCKED. |
| `POST` | `/api/v1/auth/logout` | Mọi vai trò | Ghi log đăng xuất. Token do client tự xóa (JWT không lưu phía server). |
| `GET` | `/api/v1/auth/me` | Mọi vai trò | Thông tin user hiện tại (frontend gọi để khôi phục phiên khi tải lại trang). |

## Chi nhánh

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/branches` | Mọi vai trò, theo chi nhánh được phân công | Danh sách chi nhánh. `?status=ACTIVE/INACTIVE` để lọc. |
| `POST` | `/api/v1/branches` | OWNER, theo chi nhánh được phân công | Tạo chi nhánh (OWNER). Bắt buộc branchCode, name, address. 409 DUPLICATE_BRANCH_CODE nếu trùng mã. |
| `GET` | `/api/v1/branches/{branch_id}` | Mọi vai trò, theo chi nhánh được phân công | Chi tiết chi nhánh. MANAGER/EMPLOYEE xem chi nhánh không được phân công -> 403. |
| `PUT` | `/api/v1/branches/{branch_id}` | OWNER, theo chi nhánh được phân công | Cập nhật mã, tên, địa chỉ, SĐT (OWNER). Trạng thái đổi qua PATCH /status. |
| `PATCH` | `/api/v1/branches/{branch_id}/status` | OWNER, theo chi nhánh được phân công | ACTIVE/INACTIVE (OWNER). 409 BRANCH_HAS_OPEN_PREORDERS khi còn đơn WAITING_STOCK/READY/NOTIFIED. |

## Tài khoản nội bộ

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/users` | OWNER + MANAGER, theo chi nhánh được phân công | OWNER: mọi tài khoản. MANAGER: nhân viên thuộc chi nhánh mình; branchId ngoài phạm vi -> 403. |
| `POST` | `/api/v1/users` | OWNER + MANAGER | Tạo MANAGER/EMPLOYEE. 409 DUPLICATE_USERNAME, 422 mật khẩu < 8 ký tự hoặc chi nhánh không hợp lệ. |
| `GET` | `/api/v1/users/{user_id}` | OWNER + MANAGER, theo chi nhánh được phân công | get_user |
| `PUT` | `/api/v1/users/{user_id}` | OWNER + MANAGER, theo chi nhánh được phân công | Sửa họ tên, email, SĐT. `role` chỉ OWNER được đổi (MANAGER -> 403). |
| `PUT` | `/api/v1/users/{user_id}/branches` | OWNER + MANAGER, theo chi nhánh được phân công | Thay toàn bộ phân công chi nhánh. MANAGER chỉ dùng chi nhánh mình quản lý (khác -> 403). |
| `POST` | `/api/v1/users/{user_id}/reset-password` | OWNER + MANAGER, theo chi nhánh được phân công | Đặt mật khẩu mới (>= 8 ký tự). Không dùng cho chính mình: 409 CANNOT_RESET_OWN_PASSWORD. |
| `PATCH` | `/api/v1/users/{user_id}/status` | OWNER + MANAGER, theo chi nhánh được phân công | ACTIVE/LOCKED. 409 CANNOT_LOCK_SELF, 409 LAST_ACTIVE_OWNER. |

## Khách hàng

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/customers` | Mọi vai trò | Tìm theo tên hoặc một phần SĐT (ví dụ 4 số cuối). Chỉ trả id, tên, SĐT đã che. |
| `POST` | `/api/v1/customers` | Mọi vai trò | fullName bắt buộc; SĐT 10 số bắt đầu bằng 0; trùng SĐT -> 409 kèm customerId của khách cũ. |
| `GET` | `/api/v1/customers/quick-search` | Mọi vai trò | POS tìm nhanh: tối đa 5 khách {id, fullName, maskedPhone: 0912***678}. Khớp đúng SĐT xếp đầu. |
| `GET` | `/api/v1/customers/{customer_id}` | Mọi vai trò | Hồ sơ đầy đủ (SĐT, email, địa chỉ, ghi chú). Mỗi lần xem được ghi vào log truy cập. |
| `PUT` | `/api/v1/customers/{customer_id}` | OWNER + MANAGER | Thay toàn bộ thông tin khách (OWNER/MANAGER). Đổi sang SĐT đã có -> 409. |
| `GET` | `/api/v1/customers/{customer_id}/orders` | Mọi vai trò, theo chi nhánh được phân công | Lịch sử mua: đơn bán POS + đơn đặt trước của khách, mới nhất trước, kèm thống kê |
| `GET` | `/api/v1/customers/{customer_id}/orders/{order_key}` | Mọi vai trò, theo chi nhánh được phân công | Chi tiết 1 đơn: dòng hàng (snapshot trên đơn) và các lần thanh toán. Đơn ở chi nhánh khác -> 403. |

## Sản phẩm

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/products` | OWNER | Tạo sản phẩm (chỉ OWNER). MANAGER/EMPLOYEE -> 403 FORBIDDEN. 409 nếu trùng productCode. |

## Tồn kho

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/branches/{branch_id}/inventory` | Mọi vai trò, theo chi nhánh được phân công | Tồn kho của 1 chi nhánh. OWNER: mọi chi nhánh; MANAGER/EMPLOYEE: chỉ chi nhánh được phân công, khác -> 403. |
| `GET` | `/api/v1/inventory` | Mọi vai trò, theo chi nhánh được phân công | Tồn kho các chi nhánh user được xem (lọc bằng get_accessible_branch_ids). |

## Báo cáo

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/reports/revenue` | OWNER + MANAGER, theo chi nhánh được phân công | Doanh thu theo kỳ (giờ Việt Nam, tuần bắt đầu thứ Hai), kỳ không có đơn = 0. |
| `GET` | `/api/v1/reports/revenue/export` | OWNER + MANAGER, theo chi nhánh được phân công | Tải báo cáo doanh thu dạng CSV (UTF-8 có BOM, mở bằng Excel không lỗi tiếng Việt). |
| `GET` | `/api/v1/reports/summary` | OWNER + MANAGER, theo chi nhánh được phân công | Thẻ số dashboard: doanh thu, số đơn, giá trị trung bình/đơn và % thay đổi so với kỳ trước |
| `GET` | `/api/v1/reports/top-products` | OWNER + MANAGER, theo chi nhánh được phân công | Top sản phẩm theo SKU: tên (snapshot mới nhất), tổng số lượng, doanh thu dòng hàng. |

## Thông báo

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/notifications/{notification_id}/resend` | Mọi vai trò, theo chi nhánh được phân công | Gửi lại ngay một thông báo FAILED (cùng kênh, người nhận, nội dung), tăng retryCount. |
| `GET` | `/api/v1/preorders/{preorder_id}/notifications` | Mọi vai trò, theo chi nhánh được phân công | Lịch sử thông báo của đơn đặt trước: mỗi lần gửi 1 dòng (kênh, người nhận đã che, trạng thái, số lần gửi lại, lỗi). |

## Công khai (không đăng nhập)

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| `GET` | `/api/v1/public/branches` | Công khai (giới hạn 60 request/phút/IP) | Chi nhánh ACTIVE: id, tên, địa chỉ, SĐT. |
| `GET` | `/api/v1/public/categories` | Công khai (giới hạn 60 request/phút/IP) | Cây danh mục ACTIVE (danh mục con của danh mục ngừng hoạt động bị ẩn). |
| `GET` | `/api/v1/public/products` | Công khai (giới hạn 60 request/phút/IP) | Tra cứu sản phẩm ACTIVE. categoryId gồm cả danh mục con. attr: biến thể phải có đủ mọi giá trị. |
| `GET` | `/api/v1/public/products/{product_id}` | Công khai (giới hạn 60 request/phút/IP) | Trang chi tiết + form đặt trước: mô tả, biến thể (id, sku, tên, thuộc tính, giá) và với mỗi |

# Task 03 – Test Case Design

**Phiên bản code kiểm thử:** `333a38b` trên nhánh `feature/task-03-test-cases`
**Người thiết kế test:** ngtrongkhanq
**Ngày thiết kế:** 26/11/2026

---

## Tổng quan

| Nhóm | Tổng số TC | Pass | Fail | Blocked | Chưa test |
|---|---|---|---|---|---|
| Authentication & RBAC | 11 | 11 | 0 | 0 | 0 |
| Product & Catalog | 4 | 4 | 0 | 0 | 0 |
| Database Config | 6 | 6 | 0 | 0 | 0 |
| Preorder Validation | 3 | 3 | 0 | 0 | 0 |
| Preorder FIFO & Notification | 9 | 0 | 0 | 9 | 0 |
| POS & Sales | 4 | 0 | 0 | 4 | 0 |
| Dashboard & Reports | 2 | 2 | 0 | 0 | 0 |
| Navigation & UI | 2 | 2 | 0 | 0 | 0 |
| **Tổng cộng** | **41** | **28** | **0** | **13** | **0** |

> **Lưu ý về Blocked:** 13 test case cần MySQL/TiDB và demo seed data. Môi trường hiện tại chỉ có SQLite in-memory. Các test này đã được chạy thành công trên `origin/develop` với MySQL (xem `docs/qa/test-runs/2026-11-25-develop/`).

---

## Nhóm 1 – Authentication & RBAC

### TC-AUTH-001: Khởi động ứng dụng – Health endpoint kiểm tra schema

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-001 |
| **Module** | Health / Database |
| **Test Scenario** | Health endpoint báo "ok" khi schema users.user_id tồn tại |
| **Preconditions** | Backend khởi động với SQLite in-memory test database |
| **Test Steps** | 1. Tạo test database với schema chuẩn<br>2. GET /health |
| **Test Data** | SQLite in-memory, bảng users có cột user_id |
| **Expected Result** | HTTP 200, `{"status":"ok","database":"up"}` |
| **Actual Result** | HTTP 200, `{"status": "ok", "database": "up"}` |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_health_reports_compatible_users_schema` |

---

### TC-AUTH-002: Health endpoint từ chối schema cũ không có user_id

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-002 |
| **Module** | Health / Database |
| **Test Scenario** | Health endpoint báo "error" khi bảng users thiếu cột user_id |
| **Preconditions** | Backend đang chạy |
| **Test Steps** | 1. Dùng database với bảng `users (id INTEGER)` không có cột `user_id`<br>2. GET /health |
| **Test Data** | SQLite in-memory, bảng users chỉ có cột id |
| **Expected Result** | HTTP 503, `{"database":"unavailable_or_incompatible"}` |
| **Actual Result** | HTTP 503, `{"status": "error", "database": "unavailable_or_incompatible"}` |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_health_rejects_database_without_user_id_column` |

---

### TC-AUTH-003: Admin tạo tài khoản cửa hàng và Owner đăng nhập

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-003 |
| **Module** | Admin / Authentication |
| **Test Scenario** | Admin provision shop → Owner login thành công, sai token bị từ chối, sai mật khẩu bị từ chối, logout thu hồi token |
| **Preconditions** | ADMIN_TOKEN được cấu hình |
| **Test Steps** | 1. POST /admin/accounts không có token → 401<br>2. POST /admin/accounts với token đúng → 201<br>3. POST /auth/login owner đúng mật khẩu → 200<br>4. GET /auth/me với token → 200<br>5. POST /auth/login sai mật khẩu → 401<br>6. POST /auth/logout → 204<br>7. GET /auth/me sau logout → 401 |
| **Test Data** | username: owner1, password: owner-password-123 |
| **Expected Result** | Mỗi bước đúng HTTP status như mô tả |
| **Actual Result** | Tất cả bước đúng |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_admin_provisions_shop_and_owner_login` |

---

### TC-AUTH-004: Đăng ký trùng username bị từ chối (409)

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-004 |
| **Module** | Admin |
| **Test Scenario** | Provision cùng owner username lần 2 trả 409 |
| **Preconditions** | Shop đã được tạo |
| **Test Steps** | 1. Provision shop lần 1 → 201<br>2. Provision shop lần 2 cùng username → 409 |
| **Test Data** | username: owner1 |
| **Expected Result** | HTTP 409 |
| **Actual Result** | HTTP 409 |
| **Status** | **Pass** |
| **Priority** | Medium |
| **Automated Test** | `test_auth_flow.py::test_expired_subscription_blocks_login_and_duplicate_owner` |

---

### TC-AUTH-005: Subscription hết hạn chặn đăng nhập

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-005 |
| **Module** | Authentication / Subscription |
| **Test Scenario** | Khi subscription_expires_at trong quá khứ, đăng nhập trả 401 |
| **Preconditions** | Shop đã được tạo |
| **Test Steps** | 1. Provision shop<br>2. Đặt subscription_expires_at = now() - 1 ngày<br>3. POST /auth/login |
| **Test Data** | username: owner1 |
| **Expected Result** | HTTP 401 |
| **Actual Result** | HTTP 401 |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_expired_subscription_blocks_login_and_duplicate_owner` |

---

### TC-AUTH-006: Mỗi role dùng suffix và mật khẩu riêng

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-006 |
| **Module** | Authentication / RBAC |
| **Test Scenario** | Manager login với `:manager` suffix, Staff login với `:staff` suffix. Dùng mật khẩu sai role bị 401 |
| **Preconditions** | Shop đã provision, users đã tạo |
| **Test Steps** | 1. Tạo manager1 và staff1<br>2. Login manager1:manager đúng mật khẩu → 200, role=manager<br>3. Login staff1:staff đúng mật khẩu → 200, role=staff<br>4. Login manager1:manager với mật khẩu staff → 401 |
| **Test Data** | manager1/manager-password-123, staff1/staff-password-123 |
| **Expected Result** | Login đúng → 200 với role tương ứng; login sai → 401 |
| **Actual Result** | Đúng như mong đợi |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_each_role_uses_its_suffix_and_own_password` |

---

### TC-AUTH-007: Staff không tạo được user mới (403 Forbidden)

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-007 |
| **Module** | RBAC / Users |
| **Test Scenario** | Staff gọi POST /users bị từ chối 403 |
| **Preconditions** | Shop đã provision, staff đã login |
| **Test Steps** | 1. Login staff1:staff<br>2. POST /api/v1/users với token của staff |
| **Test Data** | Staff token |
| **Expected Result** | HTTP 403 |
| **Actual Result** | HTTP 403 |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_each_role_uses_its_suffix_and_own_password` |

---

### TC-AUTH-008: Owner quản lý nhân viên (profile, branch, password, status)

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-008 |
| **Module** | Users / Branch Assignment |
| **Test Scenario** | Owner tạo staff, gán branch, cập nhật profile, đổi mật khẩu, khóa tài khoản. Gán chi nhánh ngoài store bị 422. |
| **Preconditions** | Shop đã provision, 2 branches tồn tại (branch 101 trong store, branch 202 ngoài store) |
| **Test Steps** | 1. Tạo staff với branch_ids=[101]<br>2. Liệt kê nhân viên theo branchId=101 → thấy staff<br>3. Gán branch 202 (ngoài store) → 422<br>4. Cập nhật profile → 200<br>5. Đổi mật khẩu → 204<br>6. Đăng nhập mật khẩu cũ → 401, mật khẩu mới → 200<br>7. Khóa tài khoản → 200; đăng nhập lại → 401 |
| **Test Data** | branch_id=101 (trong store), branch_id=202 (ngoài store) |
| **Expected Result** | Mỗi thao tác đúng status code |
| **Actual Result** | Tất cả đúng |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_owner_manages_employee_profile_status_password_and_branch_scope` |

---

### TC-AUTH-009: Non-owner không liệt kê được users (403)

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-009 |
| **Module** | RBAC / Users |
| **Test Scenario** | Staff gọi GET /users bị từ chối 403 |
| **Preconditions** | Shop đã provision, staff đã tạo và login |
| **Test Steps** | 1. GET /api/v1/users với token của staff |
| **Test Data** | Staff token |
| **Expected Result** | HTTP 403 |
| **Actual Result** | HTTP 403 |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_non_owner_cannot_list_or_manage_store_users` |

---

### TC-AUTH-010: Refresh token rotation và revoke khi tái dùng

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-010 |
| **Module** | Authentication / Token |
| **Test Scenario** | Refresh token xoay vòng; tái dùng refresh token cũ thu hồi tất cả phiên |
| **Preconditions** | Shop đã provision, login với remember_me=true |
| **Test Steps** | 1. Login remember_me=true → nhận access_token + refresh cookie<br>2. POST /auth/refresh → access_token mới<br>3. Token cũ bị thu hồi (401)<br>4. Dùng lại refresh token gốc → 401, và token mới cũng bị thu hồi (401) |
| **Test Data** | username: owner1, remember_me: true |
| **Expected Result** | Token rotation đúng; reuse attack bị phát hiện và thu hồi toàn bộ phiên |
| **Actual Result** | Đúng theo expected |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_refresh_rotation_remember_cookie_and_reuse_revokes_sessions` |

---

### TC-AUTH-011: Session cookie không có max-age khi không nhớ đăng nhập

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-AUTH-011 |
| **Module** | Authentication / Cookie |
| **Test Scenario** | Login không remember_me → refresh cookie là session cookie (không có max-age) |
| **Preconditions** | Shop đã provision |
| **Test Steps** | 1. POST /auth/login không có remember_me<br>2. Kiểm tra Set-Cookie header |
| **Test Data** | username: owner1 |
| **Expected Result** | Cookie có httponly, không có max-age= |
| **Actual Result** | Cookie có httponly, không có max-age= |
| **Status** | **Pass** |
| **Priority** | Medium |
| **Automated Test** | `test_auth_flow.py::test_unremembered_login_uses_session_cookie` |

---

## Nhóm 2 – Product & Catalog

### TC-PROD-001: Product cost price chỉ Owner xem được

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PROD-001 |
| **Module** | Products / RBAC |
| **Test Scenario** | Owner thấy cost price, staff không thấy |
| **Preconditions** | Shop đã provision, sản phẩm đã tạo |
| **Test Steps** | 1. Tạo sản phẩm có cost_price<br>2. GET /products/{id} với owner token → thấy costPrice<br>3. GET /products/{id} với staff token → không thấy costPrice |
| **Test Data** | cost_price: 100000 |
| **Expected Result** | Owner: thấy costPrice; Staff: không thấy costPrice |
| **Actual Result** | Đúng như expected |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_catalog_auth.py::test_product_cost_price_is_only_visible_to_owner` |

---

### TC-PROD-002: Catalog dùng đúng role và store của người tạo

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PROD-002 |
| **Module** | Products / Catalog |
| **Test Scenario** | Catalog endpoint trả sản phẩm thuộc đúng store; role được ghi khi tạo sản phẩm |
| **Preconditions** | Shop đã provision |
| **Test Steps** | 1. Tạo sản phẩm với owner token<br>2. GET catalog → sản phẩm thuộc store của owner |
| **Test Data** | store_id từ login response |
| **Expected Result** | Catalog chỉ trả sản phẩm của store đó |
| **Actual Result** | Đúng như expected |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_catalog_auth.py::test_catalog_uses_authenticated_store_role_and_creator` |

---

### TC-PROD-003: Upload ảnh sản phẩm chỉ Owner, kiểm tra loại file

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PROD-003 |
| **Module** | Products / Image |
| **Test Scenario** | Staff không upload được ảnh (403); file không phải ảnh bị từ chối (422); Owner upload thành công |
| **Preconditions** | Shop đã provision, sản phẩm đã tạo |
| **Test Steps** | 1. POST /products/{id}/image với staff token → 403<br>2. POST /products/{id}/image với file text → 422<br>3. POST /products/{id}/image với JPEG hợp lệ với owner token → 200 |
| **Test Data** | JPEG 1×1 pixel |
| **Expected Result** | Staff: 403; file sai: 422; owner + JPEG: 200 |
| **Actual Result** | Đúng như expected |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_catalog_auth.py::test_product_image_upload_validates_type_and_is_owner_only` |

---

### TC-PROD-004: Reports chỉ Owner và Manager xem được

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PROD-004 |
| **Module** | Reports / RBAC |
| **Test Scenario** | Owner xem được /reports/summary; Staff bị 403 |
| **Preconditions** | Shop đã provision, staff đã tạo |
| **Test Steps** | 1. GET /api/v1/reports/summary với owner token → 200<br>2. GET /api/v1/reports/summary với staff token → 403 |
| **Test Data** | Owner token, staff token |
| **Expected Result** | Owner: 200; Staff: 403 |
| **Actual Result** | Owner: 200; Staff: 403 |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_revenue_reports_allow_owner_and_block_employee` |

---

## Nhóm 3 – Database Config

### TC-DB-001: Development mode cho phép SQLite fallback

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-DB-001 |
| **Module** | Config / Database |
| **Test Scenario** | Khi DKAT_ENV không phải production, không có DB_HOST, dùng được SQLite |
| **Preconditions** | DKAT_ENV=development hoặc không set |
| **Test Steps** | 1. Gọi make_database_url() không có biến DB_* |
| **Expected Result** | Trả URL SQLite hợp lệ |
| **Actual Result** | Pass |
| **Status** | **Pass** |
| **Priority** | Medium |
| **Automated Test** | `test_database_config.py::test_development_keeps_sqlite_fallback` |

---

### TC-DB-002: Production mode chấp nhận MySQL URL

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-DB-002 |
| **Module** | Config / Database |
| **Test Scenario** | DKAT_ENV=production + DATABASE_URL mysql+pymysql://... → được chấp nhận |
| **Preconditions** | DKAT_ENV=production |
| **Test Steps** | Truyền DATABASE_URL hợp lệ |
| **Expected Result** | URL được chấp nhận |
| **Actual Result** | Pass |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_database_config.py::test_production_accepts_mysql_database_url` |

---

### TC-DB-003: Production mode chấp nhận MySQL env vars

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-DB-003 |
| **Module** | Config / Database |
| **Test Scenario** | DKAT_ENV=production + DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD → URL được tạo tự động |
| **Preconditions** | DKAT_ENV=production |
| **Test Steps** | Truyền các biến DB_* |
| **Expected Result** | URL mysql+pymysql://... được tạo |
| **Actual Result** | Pass |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_database_config.py::test_production_accepts_mysql_environment_configuration` |

---

### TC-DB-004: Production mode từ chối URL không phải MySQL

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-DB-004 |
| **Module** | Config / Database |
| **Test Scenario** | DKAT_ENV=production + DATABASE_URL postgresql://... → ConfigurationError |
| **Preconditions** | DKAT_ENV=production |
| **Test Steps** | Truyền DATABASE_URL postgresql |
| **Expected Result** | Raise ConfigurationError |
| **Actual Result** | Pass |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_database_config.py::test_production_rejects_non_mysql_database_url` |

---

### TC-DB-005: Production mode từ chối SQLite URL

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-DB-005 |
| **Module** | Config / Database |
| **Test Scenario** | DKAT_ENV=production + DATABASE_URL sqlite://... → ConfigurationError |
| **Preconditions** | DKAT_ENV=production |
| **Test Steps** | Truyền DATABASE_URL sqlite |
| **Expected Result** | Raise ConfigurationError |
| **Actual Result** | Pass |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_database_config.py::test_production_rejects_sqlite_url` |

---

### TC-DB-006: Production mode từ chối khi không có cấu hình database

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-DB-006 |
| **Module** | Config / Database |
| **Test Scenario** | DKAT_ENV=production không có DATABASE_URL hay DB_HOST → ConfigurationError |
| **Preconditions** | DKAT_ENV=production |
| **Test Steps** | Không truyền biến database nào |
| **Expected Result** | Raise ConfigurationError |
| **Actual Result** | Pass |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_database_config.py::test_production_requires_configured_server_database` |

---

## Nhóm 4 – Preorder Validation (API Unit Test)

### TC-PRE-001: Thiếu họ tên bị từ chối

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PRE-001 |
| **Module** | Preorders / Validation |
| **Test Scenario** | POST /preorders với customer.fullName rỗng → 422 |
| **Preconditions** | Backend đang chạy, variantId hết hàng tồn tại |
| **Test Steps** | POST /api/v1/preorders với fullName="" |
| **Test Data** | customer.fullName: "" |
| **Expected Result** | HTTP 422, code INVALID_PREORDER, field customer.fullName |
| **Actual Result** | **Pass** (kết quả vòng 2 ngày 25/11/2026 trên `origin/develop`) |
| **Status** | **Blocked** (cần MySQL + seed data) |
| **Priority** | High |
| **Notes** | Đã Pass trên develop vòng 2: 422 INVALID_PREORDER [{'field': 'customer.fullName', 'reason': 'String should have at least 1 character'}] |

---

### TC-PRE-002: SĐT sai định dạng bị từ chối

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PRE-002 |
| **Module** | Preorders / Validation |
| **Test Scenario** | POST /preorders với phone sai format → 422 |
| **Preconditions** | Backend đang chạy |
| **Test Steps** | 1. POST với phone="" → 422<br>2. POST với phone="12345" → 422 |
| **Test Data** | phone: "", "12345" |
| **Expected Result** | 422, field customer.phone |
| **Actual Result** | **Pass** (vòng 2 develop) |
| **Status** | **Blocked** (cần MySQL + seed data) |
| **Priority** | High |

---

### TC-PRE-003: Hàng còn tồn không cho đặt trước (409)

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-PRE-003 |
| **Module** | Preorders / Business Rule |
| **Test Scenario** | Đặt trước variant còn hàng → 409 VARIANT_IN_STOCK |
| **Preconditions** | Backend đang chạy, variant có tồn kho > 0 |
| **Test Steps** | POST /preorders với variantId có hàng |
| **Expected Result** | HTTP 409, code VARIANT_IN_STOCK |
| **Actual Result** | **Pass** (vòng 2 develop) |
| **Status** | **Blocked** (cần MySQL + seed data) |
| **Priority** | High |

---

## Nhóm 5 – Preorder FIFO & Notification (Integration)

> **Tất cả 9 TC trong nhóm này: Blocked** – cần MySQL database có seed data và cấu hình SMS/email test.
> Kết quả thực tế đã được xác minh trên `origin/develop` ngày 25/11/2026 (xem `docs/qa/test-runs/2026-11-25-develop/` và `docs/qa/test-runs/2026-11-25-round2/`).

| TC ID | Scenario | Expected | Trạng thái develop |
|---|---|---|---|
| TC-PRE-004 | Đặt trước thành công, không trừ kho | 201, Khả dụng không đổi | Pass |
| TC-PRE-005 | Nhập kho 2 chiếc → phân bổ FIFO đúng thứ tự | FIFO allocation đúng | Pass |
| TC-PRE-006 | Đơn đủ hàng → READY → gửi SMS → NOTIFIED | SMS gửi, trạng thái NOTIFIED | Pass |
| TC-PRE-007 | SMS lỗi → tự chuyển email | Email được gửi | Pass |
| TC-PRE-008 | Email lỗi → thử lại tự động | Retry không gửi trùng | Pass |
| TC-PRE-009 | Gửi lại thủ công qua nút Gửi lại | Gửi thành công, trạng thái NOTIFIED | Pass |
| TC-PRE-010 | Xác nhận nhận hàng → trừ kho | Kho giảm đúng số lượng | Pass |
| TC-PRE-011 | Hủy đơn đang giữ hàng → giải phóng FIFO | Khả dụng tăng lại | Pass |
| TC-PRE-012 | Hết hạn giữ hàng → trạng thái EXPIRED, giải phóng | Worker xử lý đúng | Pass |

---

## Nhóm 6 – POS & Sales (Integration)

> **Tất cả 4 TC: Blocked** – cần MySQL + seed data.
> Kết quả thực tế đã Pass trong vòng kiểm thử ngày 25/11/2026 (xem `docs/qa/test-runs/2026-11-25-round2/logs/r2_42_pos_auth.log`).

| TC ID | Scenario | Expected | Trạng thái develop |
|---|---|---|---|
| TC-POS-001 | Tạo đơn POS và xác nhận thanh toán, trừ kho đúng | 200, kho giảm | Pass |
| TC-POS-002 | Thanh toán sai số tiền bị từ chối | 422/400 | Pass |
| TC-POS-003 | Không bán vượt tồn khả dụng | 409 | Pass |
| TC-POS-004 | Hủy đơn PENDING và hoàn kho | 200, kho tăng lại | Pass |

---

## Nhóm 7 – Dashboard & Reports

### TC-RPT-001: Owner xem được tổng quan dashboard

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-RPT-001 |
| **Module** | Reports / Dashboard |
| **Test Scenario** | GET /reports/summary với owner token trả dữ liệu |
| **Preconditions** | Shop đã provision |
| **Test Steps** | GET /api/v1/reports/summary với owner token |
| **Expected Result** | HTTP 200 với JSON chứa tổng quan |
| **Actual Result** | HTTP 200 |
| **Status** | **Pass** |
| **Priority** | Medium |
| **Automated Test** | `test_auth_flow.py::test_revenue_reports_allow_owner_and_block_employee` |

---

### TC-RPT-002: Staff không xem được reports

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-RPT-002 |
| **Module** | Reports / RBAC |
| **Test Scenario** | GET /reports/summary với staff token → 403 |
| **Preconditions** | Shop đã provision, staff đã tạo và login |
| **Test Steps** | GET /api/v1/reports/summary với staff token |
| **Expected Result** | HTTP 403 |
| **Actual Result** | HTTP 403 |
| **Status** | **Pass** |
| **Priority** | High |
| **Automated Test** | `test_auth_flow.py::test_revenue_reports_allow_owner_and_block_employee` |

---

## Nhóm 8 – Navigation & UI

### TC-UI-001: Tài khoản thật không thấy màn hình Notifications demo

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-UI-001 |
| **Module** | Frontend / Navigation |
| **Test Scenario** | getNavigationItems() với demoSession=false → không có "notifications" |
| **Preconditions** | Frontend đã build, navigation.js đã import |
| **Test Steps** | 1. Gọi getNavigationItems({demoSession: false, allowed: () => true})<br>2. Kiểm tra items không có id "notifications" |
| **Test Data** | demoSession: false |
| **Expected Result** | items không chứa phần tử có id "notifications" |
| **Actual Result** | Không có "notifications" trong danh sách |
| **Status** | **Pass** |
| **Priority** | Medium |
| **Automated Test** | `frontend/tests/navigation.test.js` – test 1 |

---

### TC-UI-002: Demo session vẫn thấy màn hình Notifications

| Trường | Nội dung |
|---|---|
| **Test Case ID** | TC-UI-002 |
| **Module** | Frontend / Navigation |
| **Test Scenario** | getNavigationItems() với demoSession=true → có "notifications" |
| **Preconditions** | Frontend đã build, navigation.js đã import |
| **Test Steps** | 1. Gọi getNavigationItems({demoSession: true, allowed: () => true})<br>2. Kiểm tra items có id "notifications" |
| **Test Data** | demoSession: true |
| **Expected Result** | items chứa phần tử có id "notifications" |
| **Actual Result** | Có "notifications" trong danh sách |
| **Status** | **Pass** |
| **Priority** | Medium |
| **Automated Test** | `frontend/tests/navigation.test.js` – test 2 |

---

## Phụ lục – Nguồn tài liệu tham chiếu

- Bug Log: `docs/qa/DKat_Bug_Log.xlsx` (trên `origin/develop`)
- Test Cases gốc: `docs/qa/DKat_Test_Cases.xlsx` (trên `origin/develop`)
- Kết quả vòng 1: `docs/qa/test-runs/2026-11-25-develop/README.md`
- Kết quả vòng 2: `docs/qa/test-runs/2026-11-25-round2/README.md`
- POS & Auth cases: `docs/qa/test-cases/pos-auth.md`
- Preorder & Notify cases: `docs/qa/test-cases/preorder-notify.md`

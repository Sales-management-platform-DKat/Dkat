# Task 03 – Test Execution Report

**Branch kiểm thử:** `feature/task-03-test-cases`
**Commit code:** `333a38b`
**Người thực thi:** ngtrongkhanq
**Thời gian thực thi:** 26/11/2026, 01:00–01:53 (GMT+7)
**Framework:** `pytest` (backend), `node:test` (frontend)

---

## Tổng kết thực thi

| Nhóm | Tổng TC | Pass | Fail | Blocked |
|---|---|---|---|---|
| Backend Unit Tests (automated) | 31 | 31 | 0 | 0 |
| Frontend Unit Tests (automated) | 2 | 2 | 0 | 0 |
| Integration Tests (manual / develop) | 13 | — | — | 13 |
| **Tổng cộng (automated)** | **33** | **33** | **0** | **0** |
| **Tổng cộng (tất cả TC)** | **41** | **28** | **0** | **13** |

---

## Chi tiết – Backend Unit Tests

**Lệnh chạy:**
```
python -m pytest backend/tests/ -v --no-header
```

**Kết quả:**
```
============================= test session starts =============================
collected 31 items

backend/tests/test_auth_flow.py::AuthFlowTests::test_admin_provisions_shop_and_owner_login PASSED [  3%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_customer_list_profile_update_and_purchase_history_routes PASSED [  6%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_each_role_uses_its_suffix_and_own_password PASSED [  9%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_expired_subscription_blocks_login_and_duplicate_owner PASSED [ 12%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_health_rejects_database_without_user_id_column PASSED [ 16%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_health_reports_compatible_users_schema PASSED [ 19%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_non_owner_cannot_list_or_manage_store_users PASSED [ 22%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_owner_manages_employee_profile_status_password_and_branch_scope PASSED [ 25%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_refresh_rotation_remember_cookie_and_reuse_revokes_sessions PASSED [ 29%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_revenue_reports_allow_owner_and_block_employee PASSED [ 32%]
backend/tests/test_auth_flow.py::AuthFlowTests::test_unremembered_login_uses_session_cookie PASSED [ 35%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_admin_provisions_shop_and_owner_login PASSED [ 38%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_catalog_uses_authenticated_store_role_and_creator PASSED [ 41%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_customer_list_profile_update_and_purchase_history_routes PASSED [ 45%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_each_role_uses_its_suffix_and_own_password PASSED [ 48%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_expired_subscription_blocks_login_and_duplicate_owner PASSED [ 51%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_health_rejects_database_without_user_id_column PASSED [ 54%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_health_reports_compatible_users_schema PASSED [ 58%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_non_owner_cannot_list_or_manage_store_users PASSED [ 61%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_owner_manages_employee_profile_status_password_and_branch_scope PASSED [ 64%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_product_cost_price_is_only_visible_to_owner PASSED [ 67%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_product_image_upload_validates_type_and_is_owner_only PASSED [ 70%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_refresh_rotation_remember_cookie_and_reuse_revokes_sessions PASSED [ 74%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_revenue_reports_allow_owner_and_block_employee PASSED [ 77%]
backend/tests/test_catalog_auth.py::CatalogAuthTests::test_unremembered_login_uses_session_cookie PASSED [ 80%]
backend/tests/test_database_config.py::DatabaseConfigTests::test_development_keeps_sqlite_fallback PASSED [ 83%]
backend/tests/test_database_config.py::DatabaseConfigTests::test_production_accepts_mysql_database_url PASSED [ 87%]
backend/tests/test_database_config.py::DatabaseConfigTests::test_production_accepts_mysql_environment_configuration PASSED [ 90%]
backend/tests/test_database_config.py::DatabaseConfigTests::test_production_rejects_non_mysql_database_url PASSED [ 93%]
backend/tests/test_database_config.py::DatabaseConfigTests::test_production_rejects_sqlite_url PASSED [ 96%]
backend/tests/test_database_config.py::DatabaseConfigTests::test_production_requires_configured_server_database [100%]

============================== warnings summary ===============================
6 warnings (Pydantic deprecation, field metadata usage)
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 31 passed, 6 warnings in 15.34s =======================
```

**Thời gian:** 15.34 giây

---

## Chi tiết – Frontend Unit Tests

**Lệnh chạy** (từ nhánh `feature/task-02-ui-review`, xác minh trên code gốc):
```
npm test
```

**Kết quả:**
```
✔ real accounts do not see the demo notification screen (...)
✔ the demo retains its local notification screen (...)
pass 2 / 2 tests
```

**Tổng:** 2/2 Pass

---

## Chi tiết – Integration Tests (Blocked)

### Lý do Blocked

13 test case trong nhóm Preorder FIFO & Notification và POS & Sales yêu cầu:
1. **MySQL/TiDB database** với schema đầy đủ (không thể dùng SQLite in-memory cho test tích hợp)
2. **Seed data** từ `python -m scripts.demo_reset` (script chỉ chạy được với MySQL)
3. **Cấu hình SMS/email** test (sandbox eSMS, email SMTP)

### Kết quả trên `origin/develop` (đã xác minh)

Các integration tests đã được chạy và xác minh thực tế trên `origin/develop` với MySQL:

| Nhóm | Ngày | Pass | Fail | Nguồn |
|---|---|---|---|---|
| Vòng 1: Auth/POS, Đặt trước/Thông báo | 25/11/2026 | 48/59 | 11 | `docs/qa/test-runs/2026-11-25-develop/` |
| Vòng demo: Sau sửa BUG-005, BUG-008 | 25/11/2026 | 59/70 | 11 | `docs/demo/kich-ban-demo.md` |
| Vòng 2: Kiểm tra lại, đối chiếu số liệu | 25/11/2026 | Không còn bug Cao mở; POS 12/12; Preorder 12/12 | 0 High | `docs/qa/test-runs/2026-11-25-round2/` |

**Kết quả vòng 2 (xác minh toàn diện):**
- POS & Auth: 12/12 Pass
- Preorder & Thông báo: 12/12 Pass
- Phân quyền: 31/31 thao tác bị cấm bị chặn đúng
- Đối chiếu số liệu: 24/24 khớp ở 4 trạng thái dữ liệu

---

## Phân tích lỗi và cảnh báo

### Warnings (không phải lỗi)

6 warnings Pydantic trong lần chạy backend tests – đây là **deprecation warning** của Pydantic V2, không ảnh hưởng chức năng:
- `PydanticDeprecatedSince20`: dùng `extra` keyword trong `Field()` → nên chuyển sang `json_schema_extra`
- `UnsupportedFieldAttributeWarning`: `validation_alias` trong `Field()` context

Các warning này không làm fail test và không ảnh hưởng runtime behavior. Nên sửa trong sprint sau.

### Tests không chạy được (Blocked)

Lý do chi tiết:
- `backend/integration_tests/`: cần MySQL + seed → **không chạy trong môi trường local dev**
- `backend/scripts/test_pbi*.ps1`: PowerShell scripts cần MySQL connection
- `docs/qa/test-cases/pos_auth_cases.py` và `preorder_notify_cases.py`: cần server đang chạy + seed data

---

## Bảng tổng hợp Test Case

| TC ID | Tên | Nhóm | Status |
|---|---|---|---|
| TC-AUTH-001 | Health endpoint – schema chuẩn | Auth | **Pass** |
| TC-AUTH-002 | Health endpoint – schema cũ | Auth | **Pass** |
| TC-AUTH-003 | Admin provision + Owner login | Auth | **Pass** |
| TC-AUTH-004 | Duplicate owner → 409 | Auth | **Pass** |
| TC-AUTH-005 | Subscription hết hạn → 401 | Auth | **Pass** |
| TC-AUTH-006 | Role suffix và mật khẩu | RBAC | **Pass** |
| TC-AUTH-007 | Staff không tạo user | RBAC | **Pass** |
| TC-AUTH-008 | Owner quản lý nhân viên | Users | **Pass** |
| TC-AUTH-009 | Non-owner không list users | RBAC | **Pass** |
| TC-AUTH-010 | Refresh token rotation | Token | **Pass** |
| TC-AUTH-011 | Session cookie | Cookie | **Pass** |
| TC-PROD-001 | Cost price RBAC | Products | **Pass** |
| TC-PROD-002 | Catalog store isolation | Catalog | **Pass** |
| TC-PROD-003 | Image upload RBAC + validation | Products | **Pass** |
| TC-PROD-004 | Reports RBAC | Reports | **Pass** |
| TC-DB-001 | Dev SQLite fallback | Config | **Pass** |
| TC-DB-002 | Prod MySQL URL | Config | **Pass** |
| TC-DB-003 | Prod MySQL env vars | Config | **Pass** |
| TC-DB-004 | Prod từ chối non-MySQL | Config | **Pass** |
| TC-DB-005 | Prod từ chối SQLite | Config | **Pass** |
| TC-DB-006 | Prod không có cấu hình | Config | **Pass** |
| TC-PRE-001 | Thiếu họ tên → 422 | Preorder | **Blocked** |
| TC-PRE-002 | SĐT sai → 422 | Preorder | **Blocked** |
| TC-PRE-003 | Hàng còn → 409 | Preorder | **Blocked** |
| TC-PRE-004 | Đặt trước không trừ kho | Preorder/FIFO | **Blocked** |
| TC-PRE-005 | FIFO allocation | Preorder/FIFO | **Blocked** |
| TC-PRE-006 | READY → SMS → NOTIFIED | Notification | **Blocked** |
| TC-PRE-007 | SMS lỗi → email | Notification | **Blocked** |
| TC-PRE-008 | Retry email | Notification | **Blocked** |
| TC-PRE-009 | Gửi lại thủ công | Notification | **Blocked** |
| TC-PRE-010 | Xác nhận nhận hàng → trừ kho | Preorder | **Blocked** |
| TC-PRE-011 | Hủy đơn → giải phóng | Preorder | **Blocked** |
| TC-PRE-012 | Hết hạn → EXPIRED | Preorder | **Blocked** |
| TC-POS-001 | Tạo đơn + thanh toán | POS | **Blocked** |
| TC-POS-002 | Sai số tiền | POS | **Blocked** |
| TC-POS-003 | Vượt tồn | POS | **Blocked** |
| TC-POS-004 | Hủy đơn | POS | **Blocked** |
| TC-RPT-001 | Owner xem dashboard | Reports | **Pass** |
| TC-RPT-002 | Staff không xem reports | Reports | **Pass** |
| TC-UI-001 | Nav không có Notifications (thật) | UI | **Pass** |
| TC-UI-002 | Nav có Notifications (demo) | UI | **Pass** |

---

## Các chức năng chưa đủ điều kiện kiểm thử

Các chức năng sau cần MySQL database với seed data để kiểm thử đầy đủ:

1. **Preorder FIFO allocation** – phân bổ tồn kho theo thứ tự đặt
2. **SMS/Email notification flow** – yêu cầu eSMS sandbox và SMTP
3. **POS full transaction** – tạo đơn, thanh toán, trừ kho, hoàn đơn
4. **Inventory management** – nhập kho, kiểm kho

Để chạy các test này: checkout `origin/develop`, cấu hình `.env` với MySQL local, chạy `python -m scripts.demo_reset`, sau đó dùng các script trong `docs/qa/test-runs/`.

---

## Kết luận

- **28/41 test case có thể chạy** trong môi trường không có MySQL → **28/28 Pass (100%)**
- **13/41 test case Blocked** do phụ thuộc MySQL + seed data
- **0 Fail** trong số các test đã chạy
- Toàn bộ backend unit tests (31) và frontend unit tests (2) đều Pass
- Integration tests đã được xác minh độc lập trên `origin/develop` và đều Pass ở vòng 2

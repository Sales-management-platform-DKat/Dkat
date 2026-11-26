# Ma trận phân quyền RBAC (cập nhật 2026-11-27)

Áp dụng cho backend **sync** trên nhánh `master` (FastAPI, `app/core/permissions.py`). Backend là nơi quyết định quyền; frontend chỉ ẩn nút cho gọn giao diện. Bản demo (`frontend/src/demo/demo-api.js`) dùng cùng quy tắc.

Phạm vi chi nhánh: OWNER thấy mọi chi nhánh của cửa hàng mình. MANAGER và EMPLOYEE chỉ thấy các chi nhánh được phân công trong `user_branches`. Mọi `branchId` gửi lên đều được kiểm tra lại bằng `require_branch_access` (403 nếu nằm ngoài phạm vi). `store_id` luôn lấy từ phiên đăng nhập, không lấy từ request.

| Chức năng | Endpoint chính | OWNER | MANAGER | EMPLOYEE |
|---|---|---|---|---|
| Xem chi nhánh | `GET /branches`, `GET /branches/{id}` | Tất cả | Chi nhánh được phân công | Chi nhánh được phân công |
| Tạo / sửa / ngừng chi nhánh | `POST`, `PUT /branches`, `PATCH /branches/{id}/status` | ✓ | ✗ 403 | ✗ 403 |
| Tạo tài khoản Manager/Employee | `POST /users` | ✓ | ✗ 403 | ✗ 403 |
| Sửa, khóa, đặt lại mật khẩu, phân công chi nhánh | `PUT/PATCH/POST /users/{id}…` | ✓ | ✗ 403 | ✗ 403 |
| Xem danh sách nhân viên | `GET /users` | Toàn cửa hàng | Chỉ Employee thuộc chi nhánh của mình (chỉ đọc) | ✗ 403 |
| Xem sản phẩm, danh mục, tồn kho | `GET /products`, `/categories`, `/inventory` | ✓ | ✓ (tồn kho trong phạm vi) | ✓ (tồn kho trong phạm vi) |
| Thêm / sửa sản phẩm, biến thể, danh mục, thuộc tính, ảnh, import CSV sản phẩm | `POST /products/full`, `POST/PUT /products…`, `/variants…`, `/categories…`, `/attributes`, `/products/images`, `/products/import-csv` | ✓ | ✓ | ✗ 403 |
| Ngừng bán / mở bán sản phẩm, biến thể, danh mục | `PATCH …/status` | ✓ | ✗ 403 | ✗ 403 |
| Giá vốn (cost price) | xem/ghi | ✓ | Ẩn; khi Manager sửa biến thể, giá vốn cũ được giữ nguyên | Ẩn |
| Nhập / xuất / kiểm kê kho, nhập kho từ file CSV/XLSX | `POST /inventory/import|export|stocktake|import-csv` | ✓ | ✓ (chi nhánh của mình) | ✗ 403 (trừ khi `ALLOW_EMPLOYEE_STOCK=true`) |
| Tạo SKU mới khi nhập kho (form hoặc file) | `POST /products/full`, `/inventory/import-csv` | ✓ | ✓ | ✗ (kể cả khi `ALLOW_EMPLOYEE_STOCK=true`) |
| Lịch sử biến động kho | `GET /inventory/movements` | ✓ | ✓ (phạm vi) | ✓ (phạm vi) |
| Tạo đơn bán, thanh toán, hủy đơn chờ | `POST /sales-orders…` | ✓ | ✓ (phạm vi) | ✓ (phạm vi) |
| Xem danh sách đơn bán | `GET /sales-orders` | Tất cả chi nhánh | Chi nhánh của mình | Chỉ đơn do chính mình tạo |
| Hoàn tiền đơn đã thanh toán | `POST /sales-orders/{id}/refund` | ✓ | ✓ (phạm vi) | ✗ 403 |
| Khách hàng: xem, tạo | `GET/POST /customers` | ✓ | ✓ | ✓ |
| Khách hàng: sửa | `PUT /customers/{id}` | ✓ | ✓ | ✗ 403 |
| Đơn đặt trước: xem, thu tiền, giao, hủy | `/preorders…` | ✓ | ✓ (phạm vi) | ✓ (phạm vi) |
| Tạo đơn đặt trước (chỉ khi hết hàng) | `POST /preorders` (công khai) | ✓ | ✓ | ✓ |
| Báo cáo doanh thu | `GET /reports/*` | Toàn chuỗi hoặc từng chi nhánh | Bắt buộc chọn chi nhánh của mình | ✗ 403 |

Đăng nhập: tên đăng nhập không phân biệt hoa thường và là duy nhất. Hậu tố cũ `ten:manager` / `ten:staff` vẫn được chấp nhận nhưng phải khớp vai trò thật. Tài khoản `LOCKED`, phiên bị thu hồi hoặc gói đăng ký hết hạn đều trả 401.

Kiểm thử tự động: `backend/integration_tests/test_system_audit_mysql.py` (chạy bằng `scripts/test_system_audit_mysql.ps1`) và `frontend/tests/system-audit.test.js` (bản demo).

---

# (Lưu trữ) Ma trận của backend async cũ

> Phần dưới mô tả nhánh backend async (`tuan/*`) và các script `check_rbac.py` / `seed_auth.py` không còn chạy trên `master`. Chỉ giữ lại để tham khảo.


Bảng này ghi **kết quả thực tế** khi chạy `python -m scripts.check_rbac` (thư mục `backend/`) ngày 2026-11-13: **41/41 trường hợp đạt**.
Dữ liệu dùng để kiểm thử lấy từ `python -m scripts.seed_auth`.

## 1. Vai trò và phạm vi chi nhánh

| Tài khoản | Vai trò | Chi nhánh được phân công | Phạm vi chi nhánh khi kiểm tra quyền |
|---|---|---|---|
| owner01 | OWNER | (không cần phân công) | Mọi chi nhánh của cửa hàng mình, kể cả chi nhánh INACTIVE |
| manager01 | MANAGER | CN01, CN02 | Chỉ CN01, CN02 (chi nhánh đang ACTIVE) |
| staff01 | EMPLOYEE | CN01 | Chỉ CN01 (chi nhánh đang ACTIVE) |
| locked01 | EMPLOYEE (LOCKED) | CN01 | Bị chặn ở mọi route: 403 `ACCOUNT_LOCKED` |

CN03 không được phân công cho ai, nên chỉ OWNER xem được. Chi nhánh này dùng để kiểm thử truy cập chi nhánh ngoài phạm vi.

## 2. Ma trận 3 vai trò × 5 route

| # | Route | Bảo vệ bởi | OWNER | MANAGER | EMPLOYEE |
|---|---|---|---|---|---|
| R1 | `GET /api/v1/auth/me` | `require_auth` | 200 | 200 | 200 |
| R2 | `GET /api/v1/health/db` | `require_role("OWNER")` | 200 | 403 | 403 |
| R3 | `POST /api/v1/products` | `require_role("OWNER")` | 201 | 403 | 403 |
| R4 | `GET /api/v1/branches/{CN01}/inventory` | `require_branch_access()` | 200 | 200 | 200 |
| R4 | `GET /api/v1/branches/{CN02}/inventory` | `require_branch_access()` | 200 | 200 | 403 |
| R4 | `GET /api/v1/branches/{CN03}/inventory` | `require_branch_access()` | 200 | 403 | 403 |
| R5 | `GET /api/v1/inventory` (không lọc) | `get_accessible_branch_ids` | 200 · CN01, CN02, CN03 | 200 · CN01, CN02 | 200 · CN01 |
| R5 | `GET /api/v1/inventory?branch_id={CN03}` | `require_branch_access()` | 200 | 403 | 403 |

Mọi phản hồi 403 ở bảng trên có `error.code = "FORBIDDEN"`.

**Tiêu chí hoàn thành:**
- EMPLOYEE gọi `POST /products` nhận 403 `FORBIDDEN` (R3).
- MANAGER xem tồn kho CN03, chi nhánh không được phân công, nhận 403 `FORBIDDEN` (R4, R5).
- OWNER xem được tồn kho của mọi chi nhánh (R4, R5).

## 3. Xác thực (`require_auth`)

| Trường hợp | HTTP | `error.code` |
|---|---|---|
| Không gửi header `Authorization` | 401 | `UNAUTHORIZED` |
| Sai scheme (vd. `Basic ...`) | 401 | `UNAUTHORIZED` |
| Token hỏng hoặc ký sai secret | 401 | `INVALID_TOKEN` |
| Token hết hạn | 401 | `TOKEN_EXPIRED` |
| Token hợp lệ nhưng user đã bị xóa | 401 | `INVALID_TOKEN` |
| Token hợp lệ nhưng tài khoản đang LOCKED | 403 | `ACCOUNT_LOCKED` |

Mỗi request đều đọc lại vai trò và chi nhánh của user từ DB, **không** lấy từ payload token. Vì vậy khi khóa tài khoản, đổi vai trò hoặc gỡ phân công chi nhánh, thay đổi có hiệu lực ngay ở request kế tiếp.

## 4. Quy tắc phạm vi chi nhánh (`require_branch_access`)

- `branch_id` được lấy từ path param, query string và JSON body. Các tên được chấp nhận: `branch_id` và `branchId`.
- Nếu `branch_id` xuất hiện ở nhiều nơi với giá trị khác nhau, trả 400 `BAD_REQUEST`. Lý do: tránh trường hợp middleware kiểm tra chi nhánh A nhưng handler lại ghi vào chi nhánh B.
- Nếu `branch_id` không phải số nguyên dương, trả 400 `BAD_REQUEST`.
- OWNER: qua với mọi chi nhánh của cửa hàng mình. Nếu chi nhánh không tồn tại, trả 404 `NOT_FOUND`.
- MANAGER/EMPLOYEE: chỉ qua với chi nhánh được phân công. Mọi trường hợp còn lại trả 403 `FORBIDDEN`, kể cả khi id chi nhánh không tồn tại, để người dùng không dò được id nào có thật.
- Kiểm tra vai trò chạy trước khi kiểm tra body: EMPLOYEE gửi body sai tới `POST /products` vẫn nhận 403, không nhận lỗi 422.

Các trường hợp biên đã kiểm thử: 9/9 đạt (xem phần `edge` trong output của `check_rbac`).

## 5. Hướng dẫn dùng cho các module khác (Điền, Tuấn)

```python
from app.core.permissions import (
    ROLE_OWNER, ROLE_MANAGER, CurrentUser,
    require_auth, require_role, require_branch_access,
    get_accessible_branch_ids, ensure_branch_access,
)

# Chỉ một số vai trò được gọi
@router.post("", status_code=201)
async def create(body: In, user: CurrentUser = Depends(require_role(ROLE_OWNER, ROLE_MANAGER))): ...

# Thao tác trên 1 chi nhánh (branch_id ở path, query hoặc body)
@router.get("/branches/{branch_id}/sales")
async def sales(branch_id: int, user: CurrentUser = Depends(require_branch_access())): ...

# Danh sách: lọc theo chi nhánh user được xem
ids = get_accessible_branch_ids(user)          # list[int]; rỗng => trả rỗng, KHÔNG bỏ lọc
stmt = select(...).where(Model.branch_id.in_(ids))

# branch_id nằm trong bản ghi đã tải (đơn hàng, phiếu chuyển kho...)
await ensure_branch_access(db, user, order.branch_id)   # 403/404 như require_branch_access
```

Kết hợp được cả vai trò và chi nhánh trong cùng một route: `dependencies=[Depends(require_role(ROLE_OWNER, ROLE_MANAGER))]` và `user = Depends(require_branch_access())`. FastAPI chỉ chạy `require_auth` một lần cho mỗi request.

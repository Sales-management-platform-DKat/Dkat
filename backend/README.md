# DKat Backend

Python 3.12+ · FastAPI · SQLAlchemy 2 (async) · MySQL (aiomysql)

## Chạy

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # sửa DB_USER / DB_PASSWORD / DB_NAME
uvicorn app.main:app --reload # hoặc: python -m app.main
```

- Health: `GET http://127.0.0.1:8000/api/v1/health` → 200
- Swagger: `http://127.0.0.1:8000/docs` (tắt khi `APP_ENV=production`)

## Cấu trúc

```
app/
  main.py                    create_app(): CORS, logger, exception handlers, /api/v1
  core/
    config.py                Settings đọc từ .env
    exceptions.py            AppError + handler lỗi tập trung
    permissions.py           require_auth / require_role / require_branch_access
    security.py              JWT (PyJWT, HS256), hash mật khẩu (bcrypt)
  db/
    base.py                  Base cho model SQLAlchemy
    session.py               engine + pool, get_db(), transaction(), standalone_transaction()
  middlewares/
    request_logger.py        log method, url, status, thời gian
  utils/
    response.py              ok(data), error_response(...), SuccessResponse[T]
    logger.py
  api/v1/router.py           gom router các module
  modules/<module>/
    router.py                route + controller (nhận request, gọi service, trả ok())
    schemas.py               Pydantic in/out
    service.py               nghiệp vụ, mở transaction
    repository.py            truy vấn SQL
    models.py                bảng SQLAlchemy
  workers/
scripts/seed.py
```

Luồng: `router → service → repository → DB`. Router không viết SQL, repository không chứa nghiệp vụ.

## Định dạng phản hồi

- Thành công: `{"success": true, "data": ...}` → trong router: `return ok(data)`
- Lỗi: `{"success": false, "error": {"code", "message", "details"}}` → `raise AppError.not_found("...")`

| Trường hợp | HTTP | code |
|---|---|---|
| `AppError.*` | theo lỗi | `NOT_FOUND`, `FORBIDDEN`, `CONFLICT`... |
| Route không tồn tại | 404 | `NOT_FOUND` |
| Sai method | 405 | `METHOD_NOT_ALLOWED` |
| Body sai schema | 422 | `VALIDATION_ERROR` (details: field, message) |
| Body không phải JSON | 400 | `INVALID_JSON` |
| Trùng khóa / sai khóa ngoại | 409 | `CONFLICT` |
| Mất kết nối DB | 503 | `DATABASE_UNAVAILABLE` |
| Lỗi khác | 500 | `INTERNAL_ERROR` (ẩn chi tiết ở production) |

## Transaction

```python
from app.db.session import get_db, transaction

@router.post("/sales")
async def create_sale(body: SaleIn, db: AsyncSession = Depends(get_db)):
    async with transaction(db):          # commit khi xong, rollback nếu có exception
        await inventory_repo.decrease(db, ...)
        sale = await sale_repo.create(db, ...)
    return ok(sale)
```

Ngoài request (worker, seed): `async with standalone_transaction() as db: ...`

## Xác thực (JWT)

| Endpoint | Mô tả |
|---|---|
| `POST /api/v1/auth/login` `{username, password}` | → `{token, tokenType, expiresIn, user:{id, fullName, username, role, storeId, branches:[{id,name}]}}`. 401 `INVALID_CREDENTIALS` (sai user hoặc mật khẩu, cùng thông báo), 403 `ACCOUNT_LOCKED`, 422 thiếu trường |
| `GET /api/v1/auth/me` | User hiện tại (khôi phục phiên khi reload) |
| `POST /api/v1/auth/logout` | Ghi log; client tự xóa token |
| `POST /api/v1/auth/change-password` `{oldPassword, newPassword}` | 400 `INVALID_OLD_PASSWORD`, 422 mật khẩu mới < 8 ký tự hoặc trùng mật khẩu cũ |

- Gửi token: header `Authorization: Bearer <token>`. Hạn 8 giờ (`JWT_EXPIRE_HOURS`). 401 `TOKEN_EXPIRED` / `INVALID_TOKEN`.
- `.env` phải có `JWT_SECRET` riêng (xem `.env.example`). bcrypt cost = `BCRYPT_ROUNDS` (mặc định 12, tối thiểu 10).
- Payload JWT: `sub`, `user_id`, `role`, `store_id`, `branch_ids`. OWNER được tất cả chi nhánh ACTIVE của cửa hàng; MANAGER/EMPLOYEE theo `user_branches`.
- Mỗi request có token sẽ đọc lại user từ DB: tài khoản bị khóa bị chặn ngay (403) dù token chưa hết hạn.
- Dữ liệu test: `python -m scripts.seed_auth` (owner01, manager01, staff01, locked01 — mật khẩu `Dkat@1234`).
- Postman: import `postman/DKat_Auth.postman_collection.json`.

## Phân quyền

```python
@router.post("", dependencies=[Depends(require_role("OWNER", "MANAGER"))])
@router.get("/branches/{branch_id}/inventory")
async def handler(branch_id: int, user = Depends(require_branch_access())): ...
ids = get_accessible_branch_ids(user)   # lọc danh sách theo chi nhánh user được xem
```

- `require_role`: sai vai trò → 403 `FORBIDDEN`.
- `require_branch_access`: lấy `branch_id`/`branchId` từ path, query, JSON body. OWNER qua mọi chi nhánh của cửa hàng; MANAGER/EMPLOYEE chỉ chi nhánh được phân công, khác → 403.
- Ma trận quyền thực tế: [docs/rbac-matrix.md](../docs/rbac-matrix.md). Kiểm tra lại: `python -m scripts.check_rbac`.

## Chi nhánh (FR-02)

| Endpoint | Quyền | Ghi chú |
|---|---|---|
| `GET /api/v1/branches?status=` | mọi vai trò | OWNER: cả cửa hàng (kể cả INACTIVE); MANAGER/EMPLOYEE: chi nhánh được phân công |
| `GET /api/v1/branches/{id}` | mọi vai trò | ngoài phạm vi → 403, OWNER id không tồn tại → 404 |
| `POST /api/v1/branches` `{branchCode, name, address, phone?}` | OWNER | 201 + `inventoryRowsCreated` (tồn kho = 0 cho biến thể ACTIVE); thiếu trường → 422; trùng mã → 409 `DUPLICATE_BRANCH_CODE` |
| `PUT /api/v1/branches/{id}` | OWNER | thay toàn bộ mã/tên/địa chỉ/SĐT; trùng mã → 409 |
| `PATCH /api/v1/branches/{id}/status` `{status}` | OWNER | `ACTIVE`/`INACTIVE`; còn đơn đặt trước WAITING_STOCK/READY/NOTIFIED → 409 `BRANCH_HAS_OPEN_PREORDERS` |

- Không có DELETE (405): chi nhánh chỉ chuyển INACTIVE. MANAGER/EMPLOYEE mất quyền vào chi nhánh INACTIVE.
- `branchCode` được chuyển thành chữ hoa; so trùng không phân biệt hoa/thường.
- Mở lại chi nhánh (ACTIVE) sẽ bổ sung dòng tồn kho còn thiếu cho biến thể tạo trong lúc đóng.
- Postman: `postman/DKat_Branches.postman_collection.json` (40 request, chạy theo thứ tự; cần `python -m scripts.seed_auth`).

## Tài khoản nội bộ (FR-01.3)

| Endpoint | Ghi chú |
|---|---|
| `GET /api/v1/users?branchId&role&status&keyword&page&pageSize` | `{items, page, pageSize, total, totalPages}`; `pageSize` ≤ 100 (mặc định 20); `keyword` tìm trong username, họ tên, email, SĐT; `branchId` ngoài phạm vi → 403 |
| `GET /api/v1/users/{id}` | chi tiết kèm `branches: [{id, branchCode, name, status}]` |
| `PUT /api/v1/users/{id}/branches` `{branchIds}` | thay toàn bộ phân công (FR-02.4), chỉ ghi phần chênh lệch, không trùng cặp; OWNER → 409 `OWNER_HAS_ALL_BRANCHES` |
| `POST /api/v1/users` `{username, password, fullName, email?, phone?, role, branchIds}` | 201; `role` chỉ `MANAGER`/`EMPLOYEE`; mật khẩu >= 8 ký tự (bcrypt); trùng username → 409 `DUPLICATE_USERNAME` |
| `PUT /api/v1/users/{id}` `{fullName, email?, phone?, role?}` | thay họ tên/email/SĐT; `role` chỉ OWNER được đổi |
| `PATCH /api/v1/users/{id}/status` `{status}` | `ACTIVE`/`LOCKED`; tự khóa mình → 409 `CANNOT_LOCK_SELF`; khóa OWNER đang hoạt động duy nhất → 409 `LAST_ACTIVE_OWNER` |
| `POST /api/v1/users/{id}/reset-password` `{newPassword}` | không dùng cho chính mình → 409 `CANNOT_RESET_OWN_PASSWORD` (dùng `/auth/change-password`) |

- Chỉ OWNER và MANAGER gọi được (EMPLOYEE → 403). OWNER quản lý mọi tài khoản của cửa hàng.
- MANAGER chỉ quản lý tài khoản EMPLOYEE có **toàn bộ** chi nhánh ACTIVE nằm trong chi nhánh mình quản lý. Chỉ được tạo EMPLOYEE và gán vào chi nhánh của mình. Ngoài phạm vi → 403, kể cả id không tồn tại.
- Response không bao giờ có `password_hash`. Khóa tài khoản có hiệu lực ngay: login → 403 `ACCOUNT_LOCKED`, token cũ cũng bị chặn.
- Phân công: MANAGER chỉ dùng chi nhánh mình quản lý; phân công vào chi nhánh INACTIVE ngoài phạm vi của MANAGER được giữ nguyên. Thay đổi có hiệu lực ngay ở request kế tiếp (token cũ mất quyền chi nhánh bị gỡ) và khi đăng nhập lại.
- Postman: `postman/DKat_Users.postman_collection.json` (55 request), `postman/DKat_UserBranches.postman_collection.json` (42 request). Mỗi lần chạy tạo tài khoản test và khóa lại ở cuối.

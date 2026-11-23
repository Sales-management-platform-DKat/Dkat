# DKat: nền tảng quản lý bán hàng nhiều chi nhánh

DKat gồm hai phần chạy độc lập:

| Phần | Công nghệ | Trạng thái |
|---|---|---|
| `backend/` | Python, FastAPI, SQLAlchemy 2 (async), MySQL 8 | API thật: đăng nhập và phân quyền RBAC, chi nhánh, tài khoản, khách hàng, tra cứu công khai, báo cáo doanh thu, thông báo đặt trước (email/SMS) |
| `frontend/` | React 19, Vite 7 | Bản demo giao diện. Dữ liệu giả lưu trong trình duyệt (localStorage), **chưa gọi backend** |

> Mã nguồn đầy đủ của backend nằm trên nhánh **`tuan/project-docs`**. Nhánh `master` vẫn là phiên bản cũ.

Hướng dẫn dưới đây giả định chạy trên Windows (PowerShell). Trên macOS/Linux, các lệnh tương đương được ghi kèm.

---

## 1. Yêu cầu môi trường

| Công cụ | Phiên bản | Ghi chú |
|---|---|---|
| Git | bất kỳ | |
| Python | **3.12 trở lên** (đã thử với 3.14) | Khi cài trên Windows, chọn *Add python.exe to PATH* |
| MySQL Server | **8.0** | Cần biết tài khoản (ví dụ `root`) và mật khẩu. **Không cần** công cụ dòng lệnh `mysql`: DB được tạo bằng script Python |
| Node.js | **22.12 trở lên** | Chỉ cần cho frontend |

Kiểm tra nhanh: `python --version`, `node --version`, và dịch vụ MySQL đang chạy (Windows: `Get-Service MySQL*` báo `Running`).

## 2. Lấy mã nguồn

```powershell
git clone https://github.com/Sales-management-platform-DKat/Dkat.git
cd Dkat
git checkout tuan/project-docs
```

## 3. Chạy backend

Mọi lệnh trong mục này chạy **trong thư mục `backend/`**.

### 3.1 Cài thư viện

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Nếu PowerShell báo không được chạy script khi `activate`, chạy `Set-ExecutionPolicy -Scope Process Bypass` rồi thử lại.

### 3.2 Cấu hình `.env`

```powershell
copy .env.example .env             # macOS/Linux: cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mở `backend/.env` và sửa **bắt buộc**:

| Biến | Giá trị |
|---|---|
| `DB_HOST`, `DB_PORT` | Mặc định `127.0.0.1`, `3306` |
| `DB_USER`, `DB_PASSWORD` | Tài khoản MySQL của bạn |
| `DB_NAME` | Tên database sẽ được tạo, mặc định `dkat`. Nếu máy đã có database tên này, đặt tên khác |
| `JWT_SECRET` | Chuỗi ngẫu nhiên vừa sinh ở lệnh trên |

**Không bắt buộc:** các nhóm `SMTP_*` (gửi email) và `ESMS_*` (gửi SMS qua eSMS.vn). Để trống thì hệ thống vẫn chạy bình thường. Khi đó các thông báo đặt trước được ghi vào bảng `notifications` với trạng thái `FAILED` và lý do `NOT_CONFIGURED`, không làm lỗi nghiệp vụ. Ý nghĩa từng biến có ghi chú ngay trong `.env.example`.

### 3.3 Tạo database (20 bảng)

```powershell
python -m scripts.init_db
```

Lệnh này đọc `.env`, tạo database `DB_NAME` (utf8mb4) và 20 bảng từ `database/00_schema_full.sql`. Kết quả mong đợi: `OK: database dkat có 20 bảng`. Chạy lại nhiều lần vẫn an toàn.

Cách khác, không cần Python: mở MySQL Workbench, chạy `CREATE DATABASE dkat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; USE dkat;`, rồi chạy file `database/00_schema_full.sql`.

### 3.4 Nạp dữ liệu mẫu (chạy đúng thứ tự)

```powershell
python -m scripts.seed_auth        # cửa hàng, 3 chi nhánh CN01-CN03, 4 tài khoản demo, sản phẩm mẫu, 1 đơn đặt trước
python -m scripts.seed_catalog     # danh mục, thuộc tính, sản phẩm cho trang tra cứu công khai
python -m scripts.seed_sales       # 15 đơn mẫu cho báo cáo doanh thu (năm 2025-2026)
```

Các script này chạy lại nhiều lần vẫn an toàn, không tạo dữ liệu trùng.

### 3.5 Chạy server

```powershell
uvicorn app.main:app --reload
```

| Địa chỉ | Nội dung |
|---|---|
| http://127.0.0.1:8000/api/v1/health | `{"success": true, "data": {"status": "ok", "database": "up", ...}}` |
| http://127.0.0.1:8000/docs | Swagger UI: thử trực tiếp mọi API (bấm **Authorize**, dán token) |

### 3.6 Tài khoản demo

Mật khẩu chung: **`Dkat@1234`**

| Tên đăng nhập | Vai trò | Chi nhánh | Dùng để thử |
|---|---|---|---|
| `owner01` | OWNER (chủ cửa hàng) | Tất cả | Toàn quyền: chi nhánh, tài khoản, báo cáo toàn chuỗi |
| `manager01` | MANAGER | CN01, CN02 | Quản lý trong phạm vi chi nhánh; xem CN03 sẽ bị 403 |
| `staff01` | EMPLOYEE | CN01 | Nhân viên bán hàng, không xem được báo cáo |
| `locked01` | EMPLOYEE, đã khóa | CN01 | Đăng nhập bị từ chối (403 `ACCOUNT_LOCKED`) |

Đăng nhập lấy token:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"owner01\",\"password\":\"Dkat@1234\"}"
```

Gửi token ở các request sau bằng header `Authorization: Bearer <token>`.

Một số API để thử ngay:
- `GET /api/v1/reports/revenue?granularity=month&from=2026-01-01&to=2026-12-31`
- `GET /api/v1/reports/revenue/export?granularity=day&from=2026-11-01&to=2026-11-30` (tải file CSV, mở bằng Excel)
- `GET /api/v1/public/products` (không cần đăng nhập)

### 3.7 Tự kiểm tra (không cần bật server)

Các script dưới đây chạy ứng dụng ngay trong tiến trình, trên database thật, và in `PASS`/`FAIL` cho từng trường hợp:

```powershell
python -m scripts.check_rbac             # phân quyền: 3 vai trò x 5 route
python -m scripts.check_public_catalog   # tra cứu công khai, không lộ dữ liệu nội bộ, giới hạn tốc độ
python -m scripts.check_customer_orders  # lịch sử mua của khách (tự tạo rồi tự xóa dữ liệu thử)
python -m scripts.check_revenue          # doanh thu khớp truy vấn tay ở 8 mốc
python -m scripts.check_dashboard        # thẻ số và top sản phẩm
python -m scripts.check_revenue_export   # file CSV khớp API
python -m scripts.check_templates        # nội dung thông báo 2 mẫu x 2 kênh
python -m scripts.check_api_docs         # tài liệu API khớp API thật
```

Ngoài ra có các bộ Postman trong `backend/postman/` (cần bật server): import vào Postman rồi chạy *Run collection*, hoặc chạy `npx newman run postman/DKat_Branches.postman_collection.json`.

## 4. Chạy frontend (bản demo)

```powershell
cd frontend
npm ci
npm run dev                        # mở địa chỉ Vite in ra, mặc định http://127.0.0.1:5173
```

- `npm test`: kiểm thử logic nghiệp vụ giả lập. `npm run build`: build bản production vào thư mục `dist/` (xem bằng `npm run preview`, không mở trực tiếp file `dist/index.html`).
- Bản demo vào thẳng màn hình quản trị mà không cần đăng nhập. Dữ liệu giả lưu trong localStorage với key `dkat-demo-v1`; xóa key này trong DevTools để làm mới dữ liệu.
- Frontend **chưa kết nối backend**. `src/api.js` là lớp gọi HTTP đã chuẩn bị sẵn, đọc địa chỉ backend từ biến `VITE_API_BASE_URL` (xem `frontend/.env.example`).

## 5. Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [docs/api-endpoints.md](docs/api-endpoints.md) | Danh sách 38 endpoint kèm quyền truy cập, **sinh tự động từ code** |
| [docs/openapi.json](docs/openapi.json) | Đặc tả OpenAPI đầy đủ (import được vào Postman / Swagger Editor) |
| [docs/api-contract.md](docs/api-contract.md) | Hợp đồng các hàm module khác gọi trực tiếp (thông báo đặt trước, thử lại, mẫu nội dung) |
| [docs/erd.md](docs/erd.md) · [erd.png](docs/erd.png) · [erd.pdf](docs/erd.pdf) | Sơ đồ ERD 20 bảng, 34 khóa ngoại |
| [docs/rbac-matrix.md](docs/rbac-matrix.md) | Ma trận phân quyền đã kiểm thử |
| [docs/revenue-reconciliation.md](docs/revenue-reconciliation.md) | Đối chiếu báo cáo doanh thu với truy vấn tay |
| [backend/README.md](backend/README.md) | Chi tiết từng module backend: quy tắc nghiệp vụ, mã lỗi |
| `database/` | `00_schema_full.sql` (schema đầy đủ); `04`, `06`, `07`, `09` là migration cho database cũ, chạy lại nhiều lần vẫn an toàn |

Khi sửa API, chạy `python -m scripts.gen_api_docs` để cập nhật `docs/api-endpoints.md` và `docs/openapi.json`, rồi chạy `python -m scripts.check_api_docs`.

## 6. Sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `init_db` báo `Access denied` hoặc `Can't connect` | Kiểm tra dịch vụ MySQL đang chạy, và `DB_USER` / `DB_PASSWORD` / `DB_PORT` trong `backend/.env` |
| `/api/v1/health` trả `"database": "down"` | Như trên; hoặc chưa chạy `python -m scripts.init_db` |
| Seed báo `Run python -m scripts.seed_auth first` | Chạy seed đúng thứ tự ở mục 3.4 |
| `UnicodeEncodeError` khi in tiếng Việt ra console | `$env:PYTHONIOENCODING="utf-8"` (PowerShell) rồi chạy lại |
| Cổng 8000 hoặc 5173 đang bận | `uvicorn app.main:app --port 8001` / `npm run dev -- --port 5174` (khi đổi cổng frontend, cập nhật `CORS_ORIGINS` trong `.env`) |
| Mở file CSV bằng Excel thì dữ liệu dồn vào một cột | Máy dùng dấu `;` làm dấu phân cách danh sách: thêm `&delimiter=semicolon` vào URL xuất CSV |
| Gửi email báo `SMTP_AUTH_FAILED` | Gmail cần **App Password** (bật xác minh 2 bước), không dùng mật khẩu tài khoản. Xem `.env.example` |

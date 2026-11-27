# Báo cáo sửa lỗi lệch schema Pre-order – DKat (27/11/2026)

## 1. Nguyên nhân gốc

`GET /api/v1/preorders?page=1&size=50&branchId=30001` lỗi `(1054, "Unknown column 'p.cancel_reason' in 'field list'")` vì **TiDB production chưa được chạy migration `database/08_preorder_cancellation.sql`**.

- `cancel_reason` và `cancelled_at` là **cột chính thức** (PBI 140: hủy đơn đặt trước kèm lý do). Cả hai có trong `01_schema.sql` hiện tại và được thêm bằng script 08 cho DB tạo từ schema cũ. Code dùng đúng tên cột, nên **không đổi SQL hay API contract**.
- Dự án không có cơ chế migration tự động, cũng không có bảng ghi lịch sử migration. `create_all()` chỉ tạo bảng còn thiếu, không bao giờ `ALTER` bảng đã có. DB tạo từ bản `01_schema.sql` cũ sẽ giữ nguyên cấu trúc cũ cho đến khi ai đó chạy tay `database/0N_*.sql`, và không có gì cảnh báo việc này.
- `/health` chỉ kiểm tra `users.user_id`, nên không phát hiện được. Lỗi lại hiện ra dưới dạng "Không thể kết nối cơ sở dữ liệu" (503), khiến người xử lý tưởng là mất kết nối.

Vì không có quyền truy cập TiDB production, mình chưa xác nhận được trực tiếp những script nào còn thiếu ở đó. Công cụ ở mục 3 sẽ liệt kê chính xác khi chạy trên production. Rất có thể DB cũng đang thiếu 07 (`expires_at`) và/hoặc 09 (cột retry của `notifications`): hai script này ra đời cùng đợt và cũng được các API Pre-order dùng.

## 2. Schema trước và sau (bảng `preorders`)

| | Trước (production) | Sau khi chạy 08 |
|---|---|---|
| `cancel_reason VARCHAR(255) NULL` | không có | có |
| `cancelled_at DATETIME NULL` | không có | có |
| Index `ix_preorders_expiry (status, expires_at, preorder_id)` | không có | có |

Hai cột đều cho phép NULL nên dữ liệu hiện có vẫn hợp lệ. Đơn cũ có `cancelReason`/`cancelledAt = null`, đúng với API hiện tại.

## 3. Thay đổi

Toàn bộ thay đổi chỉ phát hiện, báo lỗi và hỗ trợ migration. Không đổi logic nghiệp vụ hay API contract.

| File | Nội dung |
|---|---|
| `backend/app/db/schema_check.py` (mới) | Danh sách 19 mục (cột, bảng, index, giá trị ENUM) mà các script 02–09 thêm vào, kèm tên script. `find_schema_drift()` chỉ đọc (dùng SQLAlchemy inspector), chỉ áp dụng cho MySQL/TiDB. |
| `backend/app/core/db_errors.py` (mới) | Lỗi 1054/1146 (thiếu cột/bảng) → 503 `{"code": "DATABASE_SCHEMA_OUTDATED", ...}` và log rõ cần chạy migration. Lỗi kết nối giữ nguyên câu cũ. |
| `backend/app/main.py` | Khi khởi động: log ERROR liệt kê mục thiếu và script cần chạy. `/health`: trả `{"status": "degraded", "database": "schema_outdated", "pendingMigrations": [...]}`, vẫn HTTP 200 để không làm nền tảng khởi động lại instance. Handler lỗi DB toàn cục dùng cùng cách phân loại. |
| `backend/app/modules/{preorders,sales,inventory,notifications,catalog}/router.py`, `preorders/public_router.py` | Dùng `database_error()` thay cho câu 503 cố định. Form đặt trước công khai vẫn trả câu chung cho khách, chỉ phần log là cụ thể hơn. |
| `backend/scripts/db_migrate.py` (mới) | Công cụ migration có kiểm soát (xem mục 6). |
| `backend/tests/test_schema_check.py` (mới) | 11 test: danh sách yêu cầu khớp với từng script trong `database/`; `01_schema.sql` mới đã có đủ; tách câu lệnh; mọi script đều chỉ bổ sung (không có lệnh phá dữ liệu); SQL phá dữ liệu bị từ chối; phân loại lỗi 1054/1146/2003. |
| `backend/integration_tests/test_schema_drift_mysql.py`, `backend/scripts/test_schema_drift_mysql.ps1` (mới) | Tái hiện đúng trạng thái production trên MySQL dùng một lần, rồi sửa và kiểm thử end-to-end. |
| `frontend/src/lib/api-errors.js`, `components/overlay/toast.js`, `locales/en.json`, `tests/notification-messages.test.js` | Hiện "Cơ sở dữ liệu chưa được cập nhật… báo quản trị viên chạy migration" (có tiếng Anh) với tiêu đề "Hệ thống cần cập nhật", thay cho "Không thể kết nối đến máy chủ". |
| `CLAUDE.md` | Ghi chú cơ chế mới và quy tắc: script tăng dần mới phải được thêm vào `REQUIREMENTS`. |

**Chống tái diễn:** thêm script `database/10_*.sql` mà quên cập nhật `REQUIREMENTS` thì `tests/test_schema_check.py` sẽ fail. DB thiếu migration sẽ hiện ngay ở log khởi động và ở `/health`, thay vì chỉ lộ ra khi một API bị lỗi.

## 4. API đã kiểm thử

Trên MySQL 8.0 dùng một lần (`dkat_schema_drift_test`), nạp đủ schema rồi xóa đúng các mục của script 08 để mô phỏng production:

1. `GET /api/v1/preorders?page=1&size=50&branchId=…` trước khi sửa: 503 `DATABASE_SCHEMA_OUTDATED`. Log ghi đúng `Unknown column 'p.cancel_reason'`. `/health` trả `degraded` và `pendingMigrations = ["08_preorder_cancellation.sql"]`.
2. `db_migrate` ở chế độ kiểm tra không ghi gì. Khi `--apply` với sai tên DB, công cụ từ chối. Khi `--apply` với đúng tên DB, công cụ chỉ chạy script 08. Chạy lại lần hai không làm gì. Dữ liệu `preorders` trước và sau giống hệt nhau.
3. Sau khi sửa: `GET /preorders` trả 200; lọc theo `branchId` (chi nhánh khác trả rỗng); phân trang `size=2` qua 3 trang; `cancelReason`/`cancelledAt` là `null` với đơn cũ.
4. `POST /preorders/{id}/cancel` lưu lý do và thời điểm. `GET /preorders/{id}` trả cùng giá trị. Lọc `status=CANCELLED` đúng. Hủy lần hai bị chặn (409).
5. Các API Pre-order khác: `POST /preorders`, nhập kho → READY/NOTIFIED kèm `expiresAt`, `GET /preorders/{id}/notifications`, `confirm-payment`, `fulfill`, và số liệu `GET /customers`.

## 5. Kết quả test

| Bộ test | Kết quả |
|---|---|
| Backend unit (`unittest discover -s tests`) | 73/73 OK |
| MySQL: schema drift (mới) | OK |
| MySQL: PBI 99, 110, 111, 121, 122, 129, system audit, default branch | Tất cả OK |
| Frontend `npm test` | 66/66 pass |
| Frontend `npm run build` | Thành công |

Ghi chú: lần chạy đầu, PBI 110/121/129 fail vì helper ghi log sang logger khác với logger mà test kiểm tra. Đã sửa để log vẫn ghi trên logger của router như trước, và chạy lại thì pass. Mình chưa kiểm thử trên một instance TiDB, mà chỉ trên MySQL 8.0.

## 6. Các bước trên production

Chạy trong `backend/` với `.env` trỏ tới TiDB production, vào giờ ít giao dịch.

1. **Sao lưu**: tạo bản backup/snapshot TiDB Cloud trước khi đổi schema.
2. **Kiểm tra (chỉ đọc):**
   ```powershell
   $env:PYTHONIOENCODING='utf-8'
   .\.venv\Scripts\python.exe -m scripts.db_migrate
   ```
   Lệnh in ra host, tên DB, phiên bản server, các mục còn thiếu và script tương ứng. Đối chiếu đúng là DB production trước khi đi tiếp.
3. **Áp dụng** (chỉ chạy các script còn thiếu, theo thứ tự):
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.db_migrate --apply --database <tên DB in ở bước 2>
   ```
   Hoặc chạy tay bằng client MySQL: `database/08_preorder_cancellation.sql` (và các script khác mà bước 2 liệt kê). Nhớ sửa dòng `USE dkat;` cho đúng tên DB.
4. **Xác minh:** chạy lại bước 2 và thấy "Schema is up to date". `GET /health` trả `"status": "ok"`. Mở màn hình Đặt trước, thử hủy một đơn thử nghiệm.
5. **Deploy** bản backend mới để có cảnh báo khi khởi động và mã lỗi `DATABASE_SCHEMA_OUTDATED`. Thứ tự bước 3 và 5 không bắt buộc: bản mới vẫn chạy được trên schema cũ.

**Lưu ý TiDB:**
- Các script chỉ bổ sung (`ADD COLUMN … NULL`, `CREATE INDEX`, `CREATE TABLE IF NOT EXISTS`) và mỗi bước đều kiểm tra `information_schema` trước khi chạy.
- `ADD COLUMN` có NULL là thay đổi metadata nhanh. `CREATE INDEX` chạy online.
- Script dùng `PREPARE … FROM @ddl`, mà TiDB hỗ trợ.
- Nếu bước 2 báo thiếu script 06: lệnh `ADD CONSTRAINT FOREIGN KEY` chỉ được TiDB thực thi từ v6.6 trở lên. Bản cũ hơn chấp nhận lệnh nhưng không kiểm tra ràng buộc.

Mình chưa commit, push hay deploy (nhánh làm việc: `fix/preorder-schema-drift`).

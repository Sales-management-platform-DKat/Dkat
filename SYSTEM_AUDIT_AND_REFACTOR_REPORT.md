# DKat – Báo cáo Audit, Sửa lỗi và Nâng cấp UX (2026-11-27)

Nhánh làm việc: `feature/task-04-overlay-components`. **Chưa commit, push hay deploy.** Không có thao tác nào chạm vào TiDB production: mọi kiểm thử chạy trên MySQL cục bộ dùng một lần (`backend/scripts/dev_isolated_mysql.ps1`) hoặc SQLite trong bộ nhớ.

Ký hiệu trạng thái: **VERIFIED** = đã sửa và có kiểm thử tự động/trình duyệt chứng minh · **FIXED** = đã sửa, kiểm tra một phần · **PARTIALLY FIXED** · **BLOCKED**.

---

## 1. Tổng quan hệ thống trước khi sửa

- Backend FastAPI + SQLAlchemy sync, MySQL/TiDB; frontend React 19 + Vite, JS thuần, `main.jsx` dạng nén một dòng.
- Hai bộ giao diện song song: màn hình "thật" (`src/features/*`) gọi API, và màn hình demo riêng trong `main.jsx` (dữ liệu `domain.js`/`seed.js`). Hai bộ khác nhau về form, bảng, luồng thao tác.
- Lỗi hiển thị dưới dạng khối `notice` đặt ở đầu hoặc cuối trang, thường nằm **phía sau** hộp thoại đang mở → người dùng không thấy lỗi.
- RBAC backend có nền tảng tốt (`require_branch_access`, `get_accessible_branch_ids`) nhưng chính sách thực tế khác yêu cầu (Manager không được thêm sản phẩm/danh mục, không xem được nhân viên).
- `backend/.env` trỏ thẳng vào TiDB production → chạy app cục bộ "mặc định" là ghi vào dữ liệu thật.

## 2–3. Danh sách lỗi, nguyên nhân gốc và trạng thái

| # | Lỗi | Nguyên nhân gốc | Trạng thái |
|---|---|---|---|
| 1 | Không thêm được chi nhánh | (a) Ở bản demo, trang chi nhánh gọi API thật không có token → luôn 401. (b) Lỗi validate (mã chi nhánh có dấu cách/dấu tiếng Việt) trả về tiếng Anh, bị đổi thành câu chung chung và hiển thị ở **đầu trang, sau hộp thoại** → người dùng tưởng "bấm không có gì xảy ra". (c) Bắt buộc tự nghĩ mã chi nhánh. (d) Danh sách chi nhánh ở thanh trên không làm mới sau khi tạo. | VERIFIED |
| 2 | Không chống trùng tên chi nhánh | Chỉ kiểm tra trùng mã | VERIFIED |
| 3 | Đăng nhập Manager/Employee "không kiểm tra đúng username" | Đăng nhập dựa vào hậu tố `ten:manager`/`ten:staff`; gõ tên thuần sẽ bị tìm như OWNER và thất bại. Username được lưu nguyên hoa/thường nhưng so sánh bằng chữ thường; trên TiDB (collation `utf8mb4_bin`) tài khoản có chữ hoa không bao giờ đăng nhập được. | VERIFIED |
| 4 | Lọc nhân viên theo vai trò `staff` luôn rỗng | So sánh với `"STAFF"` trong khi DB lưu `EMPLOYEE` | VERIFIED |
| 5 | Manager không xem được nhân viên chi nhánh; không thêm được sản phẩm/danh mục | Endpoint chỉ cho OWNER | VERIFIED |
| 6 | Manager sửa biến thể sẽ xóa giá vốn | Manager không thấy giá vốn, PUT gửi `costPrice=null` ghi đè | VERIFIED |
| 7 | Employee xem được mọi đơn của chi nhánh | Không lọc theo người tạo | VERIFIED |
| 8 | Lỗi 500 trả về text "Internal Server Error", lỗi DB trả "Database unavailable" tiếng Anh | Không có exception handler toàn cục | VERIFIED |
| 9 | Thông báo lỗi lộn xộn, trùng lặp, nằm sau modal | Mỗi trang tự `setError` vào khối notice; toast ở góc dưới, không khử trùng | VERIFIED |
| 10 | Import kho CSV kém ổn định | Header phải đúng tuyệt đối `sku,quantity,note`; không nhận `;` (Excel tiếng Việt), không hỗ trợ Excel, không có preview theo dòng, `window.confirm`, không chống nhập trùng, không biết tồn trước/sau | VERIFIED |
| 11 | Thêm sản phẩm rối | Tạo sản phẩm rồi mới tạo từng biến thể bằng hộp thoại khác; lỗi giữa chừng để lại sản phẩm không có biến thể; danh mục sửa bằng `window.prompt` | VERIFIED |
| 12 | Đặt trước áo sơ mi ở demo không theo tồn kho | Demo luôn chọn **biến thể hết hàng đầu tiên**, không cho chọn sản phẩm; trang `#/catalog` sinh mã giả `DEMO-…` không lưu gì | VERIFIED |
| 13 | POS: hết hàng thì không có lối đặt trước; không có tiền khách đưa/tiền thừa | Chưa có luồng | VERIFIED |
| 14 | POS: bấm nhanh 2 lần (máy quét mã vạch) tạo 2 dòng trùng | Đọc state `cart` cũ trong closure | VERIFIED |
| 15 | Demo và bản thật khác giao diện | Hai bộ màn hình riêng | VERIFIED (xem mục 7) |
| 16 | Footer của mọi hộp thoại bị co hẹp/lệch | CSS landing page đặt style cho thẻ `footer` toàn cục | VERIFIED |
| 17 | Job hết hạn đơn đặt trước (READY/NOTIFIED → EXPIRED) không chạy trong API | Bị mất khi merge "port compatible features"; lifespan chỉ `create_all` | VERIFIED |
| 18 | 5/6 bộ integration test MySQL cũ không chạy được | Dùng plan `pro` (đã bị khóa), thiếu `owner_email`, gọi route không có tiền tố `/api/v1` | VERIFIED (sửa test) |
| 19 | Trang "Thông báo" hiển thị dữ liệu demo cho người dùng thật | Đọc state demo | FIXED (ẩn với tài khoản thật) |

## 4. File đã chỉnh sửa / tạo mới

**Backend**
- `app/modules/auth/service.py` – đăng nhập theo username không phân biệt hoa thường, hậu tố vai trò tùy chọn nhưng phải khớp; lưu username chữ thường.
- `app/modules/admin/router.py` – chặn trùng username không phân biệt hoa thường khi cấp tài khoản.
- `app/modules/users/router.py` – Manager xem nhân viên chi nhánh (chỉ đọc), sửa lọc `staff`, trùng username không phân biệt hoa thường.
- `app/modules/branches/{router,schemas}.py` – tự sinh mã `CNxx`, chống trùng tên, thông báo tiếng Việt, khóa cửa hàng khi tạo (MySQL).
- `app/modules/products/{router,category_router,service,variant_service,variant_schemas}.py` – quyền Owner+Manager, bảo vệ giá vốn, endpoint mới `POST /products/full`.
- `app/modules/inventory/{csv_import,service,router}.py`, `app/core/spreadsheet.py` (mới) – import CSV/XLSX, preview, cảnh báo, chống nhập trùng.
- `app/modules/sales/service.py` – Employee chỉ thấy đơn của mình.
- `app/main.py` – handler lỗi DB/500 toàn cục, khởi động lại job hết hạn đặt trước.
- Thông báo "Database unavailable" → tiếng Việt: `inventory/router.py`, `preorders/router.py`, `sales/router.py`, `products/catalog_transaction.py`.
- `requirements.txt` – thêm `openpyxl`.
- Kiểm thử: `tests/test_catalog_auth.py` (cập nhật chính sách), `integration_tests/test_system_audit_mysql.py` (mới), sửa 6 bộ integration cũ.
- Script: `scripts/dev_isolated_mysql.ps1`, `scripts/test_system_audit_mysql.ps1` (mới).

**Frontend**
- Hạ tầng: `src/lib/api-errors.js` (mới), `src/auth-client.js`, `components/overlay/{toast.js,Hosts.jsx,FormDialog.jsx,overlay.css,index.js}`, `components/states.jsx` (mới), `styles/app-shared.css` (mới).
- Màn hình: `features/branches/BranchesPage.jsx`, `features/employees/EmployeesPage.jsx`, `features/products/{ProductsPage,ProductForm}.jsx`, `features/categories/CategoryManager.jsx`, `features/inventory/{InventoryPage,ImportDialog}.jsx`, `features/preorders/{PreordersPage,PreorderDialog}.jsx`, `features/pos/POSPage.jsx`, `ProductCatalog.jsx`, `main.jsx`.
- Mới: `features/customer-display/*`, `demo/demo-api.js`, `public/templates/mau-nhap-kho.{csv,xlsx}`, `tests/system-audit.test.js`.
- Tài liệu: `docs/rbac-matrix.md`, `CLAUDE.md`, bằng chứng E2E trong `docs/qa/system-audit-2026-11-27/`.

## 5. API đã chỉnh sửa (tương thích ngược)

| API | Thay đổi |
|---|---|
| `POST /auth/login` | Username không phân biệt hoa thường; `ten` = `ten:<role>` nếu role khớp; sai role → 401. Response giữ nguyên. |
| `POST /branches`, `PUT /branches/{id}` | `branchCode` thành tùy chọn (POST tự sinh, PUT giữ mã cũ); thêm 409 khi trùng tên. |
| `GET /users` | Manager được gọi (chỉ thấy Employee thuộc chi nhánh mình; `branchId` ngoài phạm vi → 403). |
| `POST/PUT /products…`, `/variants…`, `/categories…`, `/attributes`, `/products/images`, `/products/import-csv` | Mở cho MANAGER. `PATCH …/status` vẫn chỉ OWNER. |
| **`POST /products/full`** (mới) | Tạo sản phẩm + biến thể + tồn đầu kỳ trong **một transaction**; lỗi bất kỳ → không lưu gì. |
| `POST /inventory/import-csv` | Nhận thêm `.xlsx`; header linh hoạt (alias tiếng Việt, cột thừa bị bỏ qua, phân cách `,` `;` tab); response thêm `warnings`, `fileType`, `duplicateOfImportAt`, `rows[].productName/variantName/quantityBefore`; query mới `allowDuplicate`; 409 `DUPLICATE_STOCK_IMPORT` khi nhập lại cùng dữ liệu trong 24h. Mã lỗi và số dòng cũ giữ nguyên. |
| `GET /sales-orders` | EMPLOYEE chỉ nhận đơn do mình tạo. |
| Mọi API | Lỗi DB → 503, lỗi không lường trước → 500, body `{"detail": "<thông báo tiếng Việt>"}`; chi tiết chỉ ghi log server. |

## 6. Database migration

**Không tạo migration, không thay đổi schema, không sửa dữ liệu hiện có.**
- Chống nhập trùng dùng cột sẵn có `inventory_movements.reference_type/reference_id` (`STOCK_FILE` + dấu vân tay 60-bit của dữ liệu).
- Username mới được lưu chữ thường; username cũ có chữ hoa vẫn đăng nhập được (so sánh `LOWER()`), không cần sửa dữ liệu. Nếu dữ liệu cũ có hai username chỉ khác hoa/thường, hệ thống từ chối đăng nhập cả hai thay vì đoán (nên kiểm tra thủ công, xem mục 12).

## 7. Tính năng mới

- **Thông báo toàn cục**: toast góc trên phải, luôn nằm trên mọi hộp thoại, có icon/tiêu đề/nội dung, tự ẩn (lỗi máy chủ giữ đến khi đóng), dừng khi rê chuột, gộp thông báo trùng (`×2`). `notify.success/error/warning/info`.
- **Xử lý lỗi tập trung**: `ApiError` (status, code, fieldErrors, message thân thiện); 401/403/404/409/422/429/5xx/mất mạng đều có câu tiếng Việt; không bao giờ hiển thị SQL/stack trace/tiếng Anh nội bộ. Lỗi 422 gắn vào đúng ô nhập.
- **Form chuẩn** (`FormDialog`): validate tại chỗ, lỗi server hiển thị dưới từng ô, focus vào ô lỗi đầu tiên, cảnh báo khi đóng form chưa lưu, giữ dữ liệu khi API lỗi, chống bấm gửi 2 lần.
- **Chi nhánh**: danh sách + tìm/lọc, form tạo/sửa, drawer chi tiết (kèm nhân sự được phân công), ngừng/kích hoạt có xác nhận.
- **Nhân viên**: Owner quản lý đầy đủ; Manager xem chỉ đọc + số đơn đã thu/doanh thu 30 ngày của từng nhân viên.
- **Sản phẩm**: form chia nhóm A. Thông tin cơ bản, B. Hình ảnh (tải/đổi/xóa, xem trước), C. Biến thể (màu, size, SKU, giá bán, giá nhập), D. Tồn kho (tồn ban đầu tại chi nhánh đang chọn); màu/size lưu thành thuộc tính thật. Quản lý danh mục bằng drawer (cây danh mục, danh mục cha, mô tả, trạng thái).
- **Nhập kho từ file**: hộp thoại 3 bước (chọn file → kiểm tra & xem trước → kết quả), kéo-thả, file mẫu CSV/Excel, bảng hướng dẫn, tô đỏ dòng lỗi, tô vàng cảnh báo, tải báo cáo lỗi CSV, quay lại chọn file khác, không cho nhập khi còn lỗi (không nhập một phần), cảnh báo nhập trùng.
- **Đặt trước**: hộp thoại dùng chung (POS + trang Đặt trước): chọn sản phẩm hết hàng, số lượng, tạm tính, tìm khách cũ, họ tên/SĐT/địa chỉ bắt buộc → hiển thị mã đơn. POS có nút "Đặt trước" ngay trên sản phẩm hết hàng.
- **POS**: tiền khách đưa, gợi ý mệnh giá, tiền thừa, chọn phương thức, hủy đơn chờ có lý do.
- **Customer Display** (mục 13).
- **Demo = bản thật**: chế độ demo dùng chính các màn hình thật; mọi request đi vào `demo-api.js` (backend giả lập trong trình duyệt, cùng response và cùng RBAC), có nút "Đặt lại dữ liệu demo". Trang `#/catalog` đọc chung dữ liệu demo, đặt trước tạo đơn thật trong demo. Kiểm thử xác nhận **0 request** tới server trong demo.

## 8. Permission matrix

Xem `docs/rbac-matrix.md` (đã viết lại theo chính sách hiện tại). Tóm tắt:

| | Owner | Manager | Employee |
|---|---|---|---|
| Chi nhánh: tạo/sửa/ngừng | ✓ | ✗ | ✗ |
| Tài khoản: tạo/sửa/khóa/phân quyền | ✓ | ✗ (chỉ xem NV chi nhánh mình) | ✗ |
| Sản phẩm/biến thể/danh mục: thêm, sửa | ✓ | ✓ | ✗ (chỉ xem) |
| Ngừng bán sản phẩm/danh mục | ✓ | ✗ | ✗ |
| Nhập/xuất/kiểm kê/import kho | ✓ | ✓ (chi nhánh mình) | ✗ |
| Bán hàng, thanh toán, đặt trước | ✓ | ✓ | ✓ (chi nhánh mình) |
| Hoàn tiền | ✓ | ✓ | ✗ |
| Danh sách đơn bán | Tất cả | Chi nhánh mình | Đơn của mình |
| Báo cáo doanh thu | Toàn chuỗi | Chi nhánh mình | ✗ |

Mọi quyền được chặn ở backend; frontend chỉ ẩn nút. `branchId` và `store_id` luôn được kiểm tra lại với phiên đăng nhập (chống IDOR: đã kiểm thử truy cập chi nhánh khác → 403).

## 9. Kiểm thử đã chạy

| Bộ kiểm thử | Kết quả |
|---|---|
| Backend unit (`python -m unittest discover -s tests -t .`, SQLite) | **31/31 OK** |
| `integration_tests/test_system_audit_mysql.py` (mới, MySQL cục bộ) – đăng nhập (đúng/sai/không tồn tại/bị khóa/sai role), chi nhánh, RBAC, IDOR, tạo sản phẩm+tồn đầu kỳ (rollback), nhập/xuất/kiểm kê, import CSV+XLSX (dòng lỗi, âm, 0, chữ, SKU không tồn tại, dòng trùng, header sai, .xls, nhập trùng), movements, đặt trước (lưu DB, thiếu địa chỉ, còn hàng bị từ chối) | **8/8 OK** |
| 6 bộ integration MySQL cũ (PBI 99/110/111/121/122/129) | **119/120 OK**. Còn 1: `test_upgrade_migration_preserves_legacy_ready_order` cần dòng dữ liệu cũ do riêng script PBI 129 chèn trước migration 07, không chạy được trong trình chạy chung (xem mục 11). |
| Frontend (`npm test`) – 32 cũ + 10 mới (xử lý lỗi, khử trùng toast, payload Customer Display, demo RBAC, đặt trước + FIFO, import CSV demo, dữ liệu demo chỉ ở trình duyệt) | **42/42 OK** |
| E2E trình duyệt (Playwright + Edge, backend thật + MySQL cục bộ): `docs/qa/system-audit-2026-11-27/browser-e2e.mjs` | **36/36 PASS** |

Các bước E2E: đăng nhập sai mật khẩu/không tồn tại/Manager bằng tên thuần; Manager không thấy menu Chi nhánh, trang nhân viên chỉ đọc; Owner tạo chi nhánh (validate tại chỗ, mã sai, toast thành công, thanh trên tự cập nhật, trùng tên hiện toast **phía trên** hộp thoại), sửa chi nhánh; tạo sản phẩm 2 biến thể + tồn đầu kỳ (phát hiện trùng màu/size); import CSV lỗi → tô đỏ, nút xác nhận bị khóa → import file đúng → kết quả → nhập lại bị yêu cầu xác nhận, lịch sử ghi "từ file"; Staff mở Customer Display (cửa sổ riêng, không sidebar), đồng bộ sản phẩm/số lượng/giá/giảm giá/tổng, đóng và mở lại vẫn khôi phục giỏ, trạng thái đang thanh toán, tiền khách đưa/tiền thừa, thanh toán thành công kèm mã đơn; đặt trước sản phẩm hết hàng từ POS (validate + mã `PD-…`); mô phỏng popup bị chặn → cảnh báo + liên kết dự phòng; demo dùng đúng ProductForm/POS thật, 0 request tới server, đặt trước từ `#/catalog`; không có lỗi JavaScript chưa bắt.

## 10. Kết quả build

- `npm run build`: **thành công** (cảnh báo sẵn có: bundle JS ~535 kB > 500 kB, nên tách code sau).
- `python -m compileall app`: thành công.
- **Lint / type-check: không có** – dự án chưa cấu hình ESLint/ruff; các file `.ts/.tsx` là placeholder rỗng nên không có gì để type-check.

## 11. Những việc chưa xử lý được

| Hạng mục | Lý do | Trạng thái |
|---|---|---|
| Cờ "sản phẩm cho phép đặt trước" theo từng sản phẩm | Cần thêm cột vào bảng `products` trên DB production; nếu deploy code trước migration sẽ gây lỗi 500. Hiện mọi sản phẩm đang bán và hết hàng đều được đặt trước (đúng hành vi cũ). Cần nhóm quyết định và chạy migration có kế hoạch. | BLOCKED |
| Giá khuyến mãi, thương hiệu, nhiều ảnh/chọn ảnh đại diện, ảnh danh mục | Schema không có cột/bảng tương ứng; cần migration. Form hiện hỗ trợ 1 ảnh đại diện. | BLOCKED |
| File `.xls` (Excel 97–2003) | Không có thư viện an toàn trong dự án; hệ thống báo rõ "hãy lưu lại .xlsx hoặc CSV". | PARTIALLY FIXED |
| Excel trong bản demo | Demo đọc file trong trình duyệt nên chỉ hỗ trợ CSV; bản thật hỗ trợ XLSX. | PARTIALLY FIXED |
| QR thanh toán trên Customer Display | Hệ thống chưa tích hợp cổng thanh toán; theo yêu cầu không tạo QR giả. | BLOCKED |
| Gửi SMS/email khi đơn đặt trước sẵn sàng | Module `app.modules.notifications` chưa tồn tại (log "NotificationService unavailable"). | BLOCKED (có sẵn từ trước) |
| Đồng bộ UX toàn bộ các trang (Phần 11) | Đã làm lại Chi nhánh, Nhân viên, Sản phẩm, Danh mục, Kho, Đặt trước, POS và trạng thái tải/rỗng/lỗi dùng chung. **Chưa làm lại**: Tổng quan/Báo cáo (`DashboardPage`), Khách hàng, Đơn bán (còn khối lỗi cũ và vài `window.confirm`), Cài đặt (vẫn chỉ lưu cục bộ, chưa có API). | PARTIALLY FIXED |
| Danh mục công khai `#/catalog` cho cửa hàng thật | Backend chưa có API danh mục công khai; trang này là cửa hàng mẫu trên dữ liệu demo. | BLOCKED |
| `test_upgrade_migration_preserves_legacy_ready_order` | Cần chạy qua `scripts/test_pbi129_mysql.ps1` (script chèn dữ liệu cũ). Các script `test_pbi*_mysql.ps1` cũ không chạy được trên Windows PowerShell 5.1 (coi stderr của mysqld là lỗi) và đặt `DB_*` nên bật kiểm tra TLS của TiDB với MySQL cục bộ; cần sửa script theo mẫu `test_system_audit_mysql.ps1`. | PARTIALLY FIXED |
| Lint/type-check | Chưa có cấu hình trong dự án. | Không áp dụng |

## 12. Cần kiểm tra thủ công

1. **Trước khi deploy**: chạy `pip install -r requirements.txt` trên VPS (thêm `openpyxl`). Không cần migration.
2. Kiểm tra dữ liệu production có username trùng nhau chỉ khác hoa/thường không: `SELECT LOWER(username), COUNT(*) FROM users GROUP BY 1 HAVING COUNT(*) > 1;` (chỉ đọc). Nếu có, các tài khoản đó sẽ bị từ chối đăng nhập cho tới khi đổi tên.
3. Thông báo cho người dùng: Manager/Employee giờ đăng nhập bằng **tên đăng nhập thuần** (cách cũ `ten:manager` vẫn dùng được).
4. Thay đổi hành vi cần nhóm xác nhận: Manager được thêm/sửa sản phẩm và danh mục; Employee chỉ thấy đơn bán do mình tạo; job hết hạn đặt trước nay chạy mỗi giờ trong API (đơn READY quá hạn sẽ chuyển EXPIRED).
5. Thử import một file Excel thật xuất từ phần mềm kế toán/nhà cung cấp của cửa hàng.
6. Thử Customer Display trên hai màn hình vật lý và trình duyệt thực tế tại quầy (Chrome/Edge), kể cả chế độ toàn màn hình.
7. Xem ảnh chụp trong `docs/qa/system-audit-2026-11-27/`.

## 13. Hướng dẫn chạy và kiểm thử Customer Display

**Cách dùng tại quầy**
1. Đăng nhập (mọi vai trò bán hàng) → **Bán hàng POS** → chọn chi nhánh.
2. Bấm **🖥 Màn hình khách hàng**. Một cửa sổ trình duyệt riêng mở ra (`#/pos/customer-display`); kéo sang màn hình phụ, bấm ⛶ để toàn màn hình. Nhãn bên cạnh nút chuyển thành **Đã kết nối**.
3. Bán hàng bình thường: thêm/bớt sản phẩm, giảm giá, bấm **Thanh toán**, nhập tiền khách đưa → màn hình khách cập nhật ngay (danh sách, đơn giá, thành tiền, tổng, giảm giá, đang thanh toán, tiền khách đưa, tiền thừa, "Thanh toán thành công" + mã đơn trong ~9 giây rồi về màn hình chào).
4. Đóng nhầm cửa sổ khách: bấm lại nút, cửa sổ mở lại với giỏ hàng hiện tại. Bấm khi cửa sổ đang mở chỉ đưa nó lên trước, không mở thêm cửa sổ.
5. Trình duyệt chặn popup: POS hiện cảnh báo và liên kết **Mở trong tab mới**; hoặc cho phép popup cho trang này trong cài đặt trình duyệt.
6. Chỉ một màn hình: có thể mở Customer Display ở tab/cửa sổ khác, hoặc bỏ qua, POS vẫn hoạt động bình thường.

**Kỹ thuật**: đồng bộ qua `BroadcastChannel('dkat-customer-display')`, dự phòng `window.postMessage` giữa POS và cửa sổ con; tín hiệu nhịp 2 giây để hiển thị trạng thái kết nối; khi mở/mở lại, màn hình khách gửi `hello` và POS gửi lại trạng thái hiện tại. Chỉ gửi dữ liệu hiển thị (tên, biến thể, ảnh, số lượng, giá, tổng) – không token, mật khẩu, thông tin khách; không ghi vào URL hay localStorage. Màn hình khách không có nút thao tác bán hàng. Lưu ý: nếu mở POS ở hai tab cùng lúc, màn hình khách hiển thị tab cập nhật sau cùng.

**Kiểm thử tự động**: `tests/system-audit.test.js` (tính toán payload) và các bước Customer Display trong `docs/qa/system-audit-2026-11-27/browser-e2e.mjs`.

**Chạy cục bộ an toàn (không đụng TiDB)**
```powershell
# Terminal 1 – MySQL dùng một lần, ghi thông tin kết nối ra file
backend\scripts\dev_isolated_mysql.ps1 -EnvFile $env:TEMP\dkat-local.env
# Terminal 2 – API: che DB_* (một dấu cách) và dùng DKAT_DATABASE_URL tới MySQL cục bộ
# Terminal 3
cd frontend; npm run dev   # http://127.0.0.1:5173/#/login
# Kiểm thử MySQL tự động:
backend\scripts\test_system_audit_mysql.ps1
```

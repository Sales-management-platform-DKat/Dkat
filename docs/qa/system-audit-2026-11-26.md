# Audit hệ thống DKat — 26/11/2026

Branch: `fix/system-audit` (tách từ `master` @ `c63cdb0`). Commit: `bed12f2` (backend), `7fc465a` (frontend).

## 1. Tóm tắt trạng thái

| Hạng mục | Trạng thái |
|---|---|
| Owner chưa có chi nhánh nên không nhập kho/bán được | **FIXED** |
| Đăng nhập Platform Admin | **FIXED** (không có lỗi xác thực ở backend; lỗi nằm ở frontend/UX, xem mục 3) |
| Đa ngôn ngữ VI/EN | **FIXED** cho mọi màn hình đang được render (0 key thiếu, 0 chữ viết cứng, quét DOM 11 màn hình EN sạch) |
| Kiểm kê từ giao diện luôn lỗi 422 khi bỏ trống ghi chú | **FIXED** |
| POS/Đơn bán gửi `branchId=0` khi chưa có chi nhánh | **FIXED** |
| Hộp thoại native `window.confirm/prompt` | **FIXED** (thay toàn bộ 9 chỗ) |
| Chuẩn hóa toàn bộ modal (Add/Edit Product, Category, Employee, Customer, Branch, Create Order, Payment) | **PARTIALLY FIXED** — đã làm dialog kho + dialog xác nhận; các form còn lại giữ thiết kế cũ |
| Integration test MySQL cũ không chạy được | **FIXED** (7/7 bộ đạt) |
| Lint | **FIXED** — thêm ESLint (frontend); backend kiểm tra bằng pyflakes |

## 2. Lỗi phát hiện và nguyên nhân gốc

| # | Lỗi | Nguyên nhân gốc |
|---|---|---|
| B1 | Owner không nhập kho/bán hàng được | 3/4 cửa hàng trên DB thật có **0 chi nhánh**: API cấp tài khoản (`POST /admin/accounts`) tạo store + owner nhưng không tạo chi nhánh; mọi API kho/bán cần `branch_id`. |
| B2 | Khi không có chi nhánh, POS/Đơn bán/Đặt trước/Sản phẩm gửi `branchId=0` | `main.jsx`: `Number.isFinite(Number(branch))` với `branch=''` cho `0` (hữu hạn). |
| B3 | Không có thông báo vì sao không thao tác được | Thiếu trạng thái "chưa có chi nhánh" trên các trang. |
| A1 | "Admin không đăng nhập được" | Platform Admin **không có tài khoản/mật khẩu**, đăng nhập bằng mã `DKAT_ADMIN_TOKEN` (header `X-Admin-Token`). Backend kiểm tra mã đúng (đã thử: mã đúng 200, sai 401). Lỗi thực tế: mã dán vào kèm khoảng trắng/xuống dòng bị từ chối 401; thông báo lỗi chung chung không nói nguyên nhân (sai mã / server chưa cấu hình / mất kết nối); `compare_digest` với chuỗi không phải ASCII gây lỗi 500. Nhập "admin" ở `/#/login` không thể đúng vì không có tài khoản như vậy (link "Quản trị hệ thống" đã có sẵn trên trang đăng nhập). |
| I1 | Nhiều chỗ vẫn tiếng Việt khi chọn English | Website khách `LiveCatalog.jsx` (merge từ develop) viết cứng toàn bộ; dialog lịch sử thông báo chưa có bản dịch; landing demo; key tiếng Anh (`Close`, `Import CSV`, `Barcode`) không có bản tiếng Việt; ghi chú do backend sinh (`Bán đơn X`). Không có công cụ phát hiện key thiếu. |
| U1 | Kiểm kê qua giao diện luôn thất bại nếu bỏ trống ghi chú | Đặc tả PBI 82: ghi chú kiểm kê bắt buộc. Form không đánh dấu bắt buộc và gửi `note: null` → 422; lỗi lại hiển thị phía sau lớp phủ dialog nên người dùng không thấy. |
| U2 | Hộp thoại xác nhận/nhập lý do không dịch được, không đồng bộ giao diện | Dùng `window.confirm`/`window.prompt`. |
| T1 | 6 bộ integration test MySQL không chạy | Test cũ: gọi route thiếu `/api/v1`, cấp tài khoản với `plan: "pro"` không còn được phép và thiếu `owner_email`; script dựng mysqld tạm không đặt `DB_SSL_MODE=disabled`. |
| T2 | Test báo cáo doanh thu lỗi trên master | Đã sửa ở `c63cdb0` (fixture). |

## 3. Cách xử lý

### Khởi tạo chi nhánh mặc định (backend)
`backend/app/modules/branches/defaults.py` → `ensure_owner_default_branch()`, gọi trong `POST /auth/login` và `POST /auth/refresh`:
1. Chỉ chạy khi user là `OWNER` **và** là `stores.owner_user_id` của cửa hàng (manager, staff, platform admin không bao giờ tạo).
2. `SELECT ... FROM stores ... FOR UPDATE` khóa dòng cửa hàng (TiDB đang ở chế độ pessimistic).
3. Cửa hàng đã có chi nhánh (kể cả INACTIVE) → không tạo; trả chi nhánh ACTIVE có id nhỏ nhất, hoặc `inactive` nếu không còn chi nhánh hoạt động (tôn trọng việc chủ cửa hàng đã tắt).
4. Chưa có → tạo `CN01` (hoặc mã `CNxx` trống đầu tiên), tên "Chi nhánh chính" / "Main Branch" theo ngôn ngữ lúc đăng nhập, `address=''` (không bịa địa chỉ), `ACTIVE`, cùng dòng tồn kho 0 cho các biến thể ACTIVE — trong **một transaction**.
5. Unique `(store_id, branch_code)` là lớp chống trùng thứ hai: request thua cuộc nhận `IntegrityError`, rollback và dùng chi nhánh vừa được tạo.
6. Lỗi → rollback, đăng nhập vẫn thành công, trả `branch_setup: "failed"` để giao diện hướng dẫn.

API thay đổi (tương thích ngược, chỉ thêm trường tùy chọn):
- `LoginRequest.locale?: "vi" | "en"`
- `LoginResponse.default_branch_id?: int`, `branch_setup: "existing" | "created" | "inactive" | "failed" | "not_applicable"` (cả `/auth/login` và `/auth/refresh`)
- `POST /branches` dùng chung hàm tạo dòng tồn kho (không đổi hành vi).

Frontend chọn chi nhánh theo thứ tự: chi nhánh đang chọn → chi nhánh đã chọn lần trước của tài khoản (localStorage `dkat-branch:<userId>`) → `default_branch_id` → chi nhánh ACTIVE đầu tiên. Không có chi nhánh → empty state "Bạn chưa có chi nhánh hoạt động / No active branch found" với nút mở quản lý chi nhánh (owner) hoặc hướng dẫn nhờ chủ cửa hàng (nhân viên).

### Platform Admin
- Backend `require_admin_token`: bỏ khoảng trắng đầu/cuối, so sánh theo bytes.
- Frontend: `trim()` mã trước khi gửi; thông báo riêng cho 401 (sai mã), 503 (server chưa cấu hình `DKAT_ADMIN_TOKEN`), mất kết nối; lỗi API giờ mang `status`.
- Không có tài khoản admin nào được tạo, không hardcode mã, Owner/Employee dùng bearer token vẫn bị 401 ở `/admin/*` (có test).

### Đa ngôn ngữ
- `frontend/scripts/check-i18n.mjs` (`npm run check:i18n`, chạy trong `npm test`): phân tích AST mọi file đi tới được từ `main.jsx`, báo key thiếu (kể cả key dạng `a.b.c` truyền gián tiếp; key dạng chấm phải có ở cả `vi.json`) và chữ tiếng Việt viết cứng trong JSX text / `placeholder` / `title` / `aria-label`.
- Bổ sung ~150 bản dịch; `LiveCatalog` chuyển hết sang `t()`; số nhiều tiếng Anh; ghi chú biến động do hệ thống sinh được dịch khi hiển thị (`systemNote`).
- Ngôn ngữ lưu ở localStorage `dkat-language` (giữ khi đăng nhập lại), đổi ngay không cần tải lại, dialog đang mở cũng đổi theo.
- Danh từ riêng trong nội dung demo (Quận 1, Thảo Điền, tên người…) cố ý giữ nguyên.

### UX đã chuẩn hóa
- `components/confirm.jsx` — `confirmAction()`/`ConfirmHost` (cùng API với bộ `components/overlay/` đang phát triển, chưa commit): tiêu đề, mô tả, tone, lý do bắt buộc, giá trị điền sẵn, chạy request bên trong dialog, lỗi giữ nguyên dữ liệu đã nhập. Thay cho: hủy/hoàn đơn bán, hủy/thanh toán/giao đơn đặt trước, ghi CSV tồn kho, đổi tên danh mục, 4 xác nhận ở chế độ demo.
- Dialog Nhập/Xuất/Kiểm kê: mô tả thao tác, nhóm trường, placeholder hướng dẫn, trường bắt buộc có dấu `*`, nút chính có loading, chống gửi trùng, lỗi hiện trong dialog, bấm ra ngoài khi đã nhập không mất dữ liệu.
- Toast 4 loại: success / error / warning / info.
- Empty state có icon, tiêu đề, mô tả, CTA.

## 4. File thay đổi
Backend: `app/modules/branches/defaults.py` (mới), `app/modules/auth/{router,schemas}.py`, `app/modules/admin/router.py`, `app/modules/branches/router.py`, `tests/test_default_branch.py` (mới), `tests/test_admin_auth.py` (mới), `integration_tests/test_default_branch_mysql.py` (mới), 6 integration test cũ, `scripts/test_default_branch_mysql.ps1` (mới), 6 script `test_pbi*_mysql.ps1`.

Frontend: `src/main.jsx`, `src/LiveCatalog.jsx`, `src/LandingPage.jsx`, `src/PlatformAdmin.jsx`, `src/auth-client.js`, `src/i18n/index.js`, `src/locales/{vi,en}.json`, `src/styles.css`, `src/components/confirm.jsx` (mới), `src/features/{inventory,orders,preorders,products}/*Page.jsx`, `scripts/check-i18n.mjs` (mới), `tests/i18n-coverage.test.js` (mới), `eslint.config.js` (mới), `package.json` (+ `lint`, `check:i18n`, devDeps ESLint).

## 5. Database / migration
**Không thay đổi schema, không migration.** Chi nhánh mặc định dùng đúng các cột hiện có của `branches`. Không có thao tác ghi nào lên DB TiDB của nhóm trong quá trình audit (chỉ 3 truy vấn `SELECT` để chẩn đoán). Mọi test ghi dữ liệu chạy trên SQLite trong bộ nhớ hoặc mysqld tạm trong thư mục Temp.

## 6. Kiểm thử đã chạy (kết quả cuối)

| Bộ | Kết quả |
|---|---|
| Backend unit (`python -m unittest discover -s tests -t .`) | **54/54 OK** (trong đó 9 test chi nhánh mặc định, 9 test admin/token) |
| Integration MySQL — PBI 99 bán hàng/thanh toán | 16/16 OK |
| Integration MySQL — PBI 110 đặt trước công khai | 16/16 OK |
| Integration MySQL — PBI 111 import CSV | 13/13 OK |
| Integration MySQL — PBI 121 quản lý đặt trước | 23/23 OK |
| Integration MySQL — PBI 122 hoàn đơn | 16/16 OK |
| Integration MySQL — PBI 129 FIFO | 36/36 OK |
| Integration MySQL — chi nhánh mặc định (8 đăng nhập đồng thời thật, nhân viên, nhập kho → kiểm kê → bán) | 3/3 OK |
| Frontend `npm test` | **46/46 OK** |
| `npm run check:i18n` | 0 thiếu, 0 viết cứng |
| `npm run lint` | 0 lỗi (8 cảnh báo biến không dùng có từ trước) |
| `npm run build` | OK |
| pyflakes backend | không có tên chưa định nghĩa |
| E2E trình duyệt Edge (môi trường cô lập: mysqld tạm + backend + Vite) | **23/23 OK** |

E2E bao gồm: Platform Admin với mã có khoảng trắng và mã sai; owner đăng nhập lần đầu → "Main Branch" duy nhất trong DB; nhập kho 12, kiểm kê thiếu ghi chú bị chặn, kiểm kê về 10, bán POS → còn 9, đơn `PAID` thuộc đúng chi nhánh, biến động `IMPORT+12, ADJUSTMENT-2, SALE-1`; đăng nhập lại không tạo thêm chi nhánh và tự chọn chi nhánh; 11 màn hình tiếng Anh không còn chữ tiếng Việt; chuyển VI/EN liên tục, dialog đang mở đổi theo, giữ ngôn ngữ sau tải lại; ảnh chụp 390/820/1366px không tràn ngang; không lỗi console/HTTP; cửa hàng chỉ có chi nhánh INACTIVE thấy empty state + CTA và không bị tạo chi nhánh mới; hủy đơn qua dialog bắt buộc lý do.

Chạy lại integration MySQL: `powershell -ExecutionPolicy Bypass -File backend\scripts\test_<tên>_mysql.ps1` (cần MySQL Server 8.0 cài local; script tự dựng và tắt mysqld tạm).

## 7. Còn tồn tại
- **PARTIALLY FIXED** — Các form Thêm/Sửa sản phẩm, Danh mục, Nhân viên, Khách hàng, Tạo chi nhánh, Tạo đơn, Thanh toán POS chưa được thiết kế lại theo chuẩn dialog mới (đã dịch đầy đủ và hoạt động).
- Thông báo lỗi chi tiết từ backend là tiếng Việt; khi lỗi không có mã `api.error.*` trong catalog, giao diện tiếng Anh hiển thị câu chung kèm hướng dẫn thay vì lý do cụ thể.
- Tài khoản "Customer" không tồn tại trong hệ thống (khách không đăng nhập) nên không có luồng/test tương ứng.
- 7 file frontend không còn được import (`LivePreorders`, `LivePos`, `LiveOrders`, `LiveInventory`, `CsvStockImport`, `CategoriesPage`, `ProductsPage` ở gốc `src/`, `ComponentDemo`) — để nguyên, không audit i18n; nên xóa trong một PR riêng.
- Code async còn sót (`app/api/v1/router.py`, `modules/health`, `scripts/check_rbac.py`, `scripts/seed_auth.py`) vẫn chưa được dọn.

## 8. Thao tác thủ công / deploy
1. Merge `fix/system-audit` vào `master` (không cần migration).
2. Backend: cài lại `pip install -r requirements.txt` (develop đã thêm `httpx`), khởi động lại Uvicorn. Đảm bảo `DKAT_ADMIN_TOKEN` (≥ 32 ký tự) có trong môi trường production — nếu thiếu, trang quản trị sẽ báo "Máy chủ chưa cấu hình mã quản trị".
3. Frontend: `npm ci && npm run build`.
4. Sau deploy, 3 chủ cửa hàng đang chưa có chi nhánh sẽ được tạo "Chi nhánh chính" ở lần đăng nhập/refresh kế tiếp; nhắc họ bổ sung địa chỉ trong mục Chi nhánh (trường địa chỉ đang để trống và bắt buộc khi sửa).

## 9. Bổ sung: mục Cài đặt (commit sau)

**Lỗi gốc:** trang Cài đặt cũ là form demo lưu vào localStorage (`s.store`). Với tài khoản thật, bấm "Lưu cấu hình" vẫn báo thành công nhưng không gửi gì lên server. Module `backend/app/modules/stores/` chỉ có file rỗng.

**API mới** (không đổi schema; lỗi dùng 400/409 kèm `{code, message}`, không dùng 401 để không làm frontend tự đăng xuất):

| Endpoint | Quyền | Ghi chú |
|---|---|---|
| `GET /stores/me` | mọi vai trò | tên, gói, trạng thái/hạn gói, số chi nhánh, số nhân sự, `canEdit` |
| `PUT /stores/me` | OWNER | đổi tên cửa hàng (2–150 ký tự) |
| `PUT /auth/me` | mọi vai trò | họ tên, email (không trùng → `EMAIL_TAKEN`), số điện thoại |
| `POST /auth/change-password` | mọi vai trò | kiểm tra mật khẩu cũ (`CURRENT_PASSWORD_INVALID`), khác mật khẩu cũ (`PASSWORD_UNCHANGED`), ≥ 12 ký tự; đăng xuất mọi thiết bị khác, giữ thiết bị hiện tại |
| `GET /auth/sessions`, `POST /auth/sessions/revoke-others` | mọi vai trò | số phiên đang hoạt động; đăng xuất thiết bị khác |

`UserInfo` có thêm `phone` (tùy chọn).

**Giao diện:** 4 tab (Cửa hàng, Tài khoản, Bảo mật, Giao diện). Các tab giữ nguyên dữ liệu đang nhập khi chuyển qua lại. Có kiểm tra dữ liệu ngay trên form, nút Lưu chỉ bật khi có thay đổi, nút Hoàn tác, cảnh báo khi rời trang mà chưa lưu, thanh đo độ mạnh mật khẩu, cảnh báo gói sắp hết hạn (≤ 30 ngày), chọn ngôn ngữ/nền sáng-tối/chi nhánh làm việc. Mọi vai trò đều mở được Cài đặt để tự đổi mật khẩu và hồ sơ; thông tin cửa hàng chỉ đọc với Quản lý/Nhân viên. Bản demo vẫn đổi được tên cửa hàng demo; tab Tài khoản và Bảo mật báo "chỉ có ở tài khoản thật".

**Kiểm thử:** backend 62/62 (thêm 8 test `test_settings_api.py`); frontend 46/46; i18n 0 thiếu; E2E trình duyệt Cài đặt 20/20 trên môi trường cô lập, gồm: đổi tên lưu vào DB và cập nhật ngay trên menu; bắt email sai và mật khẩu xác nhận không khớp ngay trên form; sai mật khẩu cũ báo rõ và không bị đăng xuất; đổi mật khẩu đăng xuất thiết bị khác; "Đăng xuất thiết bị khác"; chỉ hiện đúng một tab; giao diện tiếng Anh không lộ tiếng Việt; nhân viên chỉ xem; màn hình 390px không tràn ngang.

**Chưa có:** giới hạn số lần thử mật khẩu cũ (chống dò mật khẩu) ở `/auth/change-password`; danh sách chi tiết từng phiên (thiết bị, thời điểm), vì bảng `auth_sessions` không lưu các thông tin này.

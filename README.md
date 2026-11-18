# DKat Frontend

Giao diện React và CSS giới thiệu DKat và mô phỏng quản trị cửa hàng nhiều chi nhánh. Mã nguồn được thiết kế theo DKat_SRS.docx, DKat_CSDL.docx và quy tắc đặt trước đã chốt. Đây là frontend demo, không phải phần mềm bán hàng production.

## Đặt tại D:\Dkat

Giải nén ZIP ở một thư mục tạm. Trong thư mục Dkat vừa giải nén, chạy PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-to-D.ps1
cd D:\Dkat
powershell -ExecutionPolicy Bypass -File .\Start-DKat.ps1
```

Script cài đặt sao lưu các file bị thay thế, giữ các file không trùng đường dẫn. Nếu dự án hiện có thay đổi riêng, kiểm tra bản sao lưu trước khi tiếp tục phát triển. Không có lệnh nào được chạy trên máy Windows của bạn từ phiên ChatGPT này.

Cần Node.js >= 22.12. Lệnh dùng ExecutionPolicy Bypass chỉ áp dụng cho tiến trình PowerShell vừa mở, không đổi chính sách toàn máy.

## Chạy thủ công

```powershell
cd D:\Dkat\frontend
npm ci
npm run dev
```

Mở URL Local mà Vite in ra. Dừng bằng Ctrl+C. Build production: `npm run build`; xem bản build: `npm run preview`. Không mở dist/index.html trực tiếp bằng file:// vì ES modules cần HTTP. ZIP đã kèm dist và lockfile, không kèm node_modules.

## Màn hình

- `/`: landing page giới thiệu DKat, tính năng, luồng preorder, FAQ và CTA vào demo.
- `/#/track/<token>`: kết quả và theo dõi đơn, lựa chọn nhận hàng khi đã thanh toán.
- `/#/login`: đăng nhập qua API FastAPI; chủ cửa hàng dùng tên gốc, quản lý thêm `:manager`, nhân viên thêm `:staff`.
- `/#/platform-admin`: màn hình quản trị hệ thống cấp tài khoản chủ cửa hàng và thời hạn gói đăng ký.
- `/#/admin/dashboard`, products, inventory, pos, orders, preorders, customers, employees, reports, branches, notifications, settings.
- Bản demo vào thẳng màn quản trị, không cần tên đăng nhập hoặc mật khẩu.
- Các form CRUD, nhập/xuất/kiểm kê, chi tiết giao dịch và hủy/hoàn dùng dialog.

## Tự thử nghiệp vụ

1. Từ landing page, chọn **Dùng thử bản demo** để vào quản trị mà không cần đăng nhập.
2. Trong Đặt trước, tạo hai yêu cầu cho một SKU đang hết; cung cấp tên và số điện thoại hoặc email.
3. Trong Kho hàng, nhập 3 sản phẩm cho SKU đó: yêu cầu đầu được phân bổ trước theo FIFO.
4. Nhập thêm 4: yêu cầu đủ hàng chuyển sang sẵn sàng; xác nhận thanh toán và nhận hàng trong Đặt trước.
5. Trong POS, thêm sản phẩm còn hàng, ghi nhận phương thức thanh toán và kiểm tra lịch sử đơn.
6. Báo cáo theo dõi doanh thu và khoản trả trước chưa giao riêng biệt.

## Backend FastAPI: cấp tài khoản và đăng nhập

Backend tự đọc `backend/.env` và dùng kết nối TiDB/MySQL được cấu hình ở đó (TLS xác minh chứng chỉ). File này không được commit; `.env.example` chỉ chứa giá trị mẫu. Nếu không cấu hình `DB_HOST`, backend dùng SQLite cục bộ làm phương án dự phòng. Đảm bảo `DKAT_ADMIN_TOKEN` trong `.env` là chuỗi ngẫu nhiên đủ mạnh, sau đó cài và chạy:

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Mã quản trị phải dài ít nhất 32 ký tự. Tạo mã mới bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"` rồi lưu vào `DKAT_ADMIN_TOKEN` trong `backend/.env`. Mở `/#/platform-admin` trong frontend, nhập mã đó, rồi tạo cửa hàng, chọn gói và thời hạn, cấp tên đăng nhập, email cùng mật khẩu ban đầu cho chủ doanh nghiệp. Mã quản trị chỉ được gửi tới API và không lưu trong trình duyệt. Mật khẩu tài khoản được băm PBKDF2; API không trả lại mật khẩu. Gửi mật khẩu khởi tạo cho chủ doanh nghiệp qua kênh riêng an toàn.

Backend ánh xạ cửa hàng và người dùng vào các bảng `stores` và `users` đã có trong DB; khi khởi động, chỉ tạo thêm `store_subscriptions` và `auth_sessions` nếu chúng chưa tồn tại. Không xóa hay ghi đè các bảng nghiệp vụ hiện có.

Đăng nhập tại `/#/login` bằng email hoặc tên đăng nhập. Tài khoản không có hậu tố được xác thực với vai trò chủ cửa hàng; hậu tố `:manager` và `:staff` lần lượt chọn tài khoản quản lý và nhân viên. Tên đăng nhập và email phải duy nhất; mỗi nhân sự có tên đăng nhập và mật khẩu riêng. Chủ cửa hàng có thể cấp tài khoản nhân sự qua `POST /api/v1/users` bằng bearer token và truyền email tùy chọn. API chấp nhận định danh trong trường `username` hoặc `email`, kiểm tra vai trò, trạng thái tài khoản và thời hạn gói trên server. Bảng quyền giao diện hiện tại: chủ cửa hàng có toàn quyền; quản lý không vào Chi nhánh/Cài đặt; nhân viên chỉ vào Sản phẩm, Kho, POS, Đơn bán, Đặt trước, Khách hàng và Thông báo.

Tạo/ghi dữ liệu nghiệp vụ của các màn hình bán hàng hiện vẫn là demo lưu trong localStorage; cần tích hợp các API nghiệp vụ tương ứng trước khi dùng dữ liệu khách hàng thực tế. Có thể đặt `DKAT_DATABASE_URL` để dùng SQLite hoặc database khác; luôn dùng HTTPS và giới hạn quyền truy cập mã quản trị.

## Phân chia mã nguồn

- `src/main.jsx`: màn hình, reusable UI và dialog. Các feature nằm trong các hàm có tên để nhóm dễ tách ra thư mục features sau khi chốt UI.
- `src/styles.css`: design tokens sáng/tối, landing, admin và responsive.
- `src/domain.js`: mô phỏng nghiệp vụ kho, POS, FIFO và báo cáo.
- `src/seed.js`: dữ liệu giả. localStorage key: dkat-demo-v1.
- `src/csv.js`: CSV UTF-8, tối đa 100 dòng, validate toàn file trước khi lưu.
- `src/api.js`: HTTP adapter để nhóm tiếp tục nối FastAPI; chưa được gọi thay cho mock trong bản này.
- `tests/domain.test.js`: kiểm thử logic trọng yếu bằng Node test runner.

## Giới hạn cần biết trước khi nối backend

- API FastAPI đã hỗ trợ cấp tài khoản, đăng nhập, phiên bearer và phân quyền theo vai trò. Các màn hình nghiệp vụ vẫn là bản demo localStorage và chưa được kết nối API.
- Không gửi SMS/email hoặc xác minh ngân hàng, không hỗ trợ thao tác nhiều nhân viên đồng thời. Chống tranh chấp phải triển khai ở backend transaction.
- Link preorder chỉ hoạt động trên trình duyệt đã tạo dữ liệu demo. Token thật phải lưu hash và được xác minh tại server.
- UI sản phẩm hiển thị biến thể theo từng dòng SKU; backend cần nối products/product_variants/attributes thay cho danh sách phẳng này.
- Báo cáo số tiền tính từ dữ liệu demo; biểu đồ trang landing và Dashboard ghi rõ minh họa. Báo cáo có bộ lọc thời gian tương đối, chưa có tổng hợp lịch theo tuần/tháng/năm.
- Font Manrope tải Google Fonts khi có mạng, tự dùng Segoe UI nếu offline. Biểu tượng và minh họa sản phẩm đều SVG/CSS, không phụ thuộc ảnh bên ngoài.
- Không có catalog/checkout công khai, trả hàng POS, cổng thanh toán, vận chuyển tích hợp, đa kênh hay chuyển kho.
- Dữ liệu localStorage không phù hợp lưu thông tin khách thật. Dùng dữ liệu giả khi thử. Có thể xóa key dkat-demo-v1 trong DevTools để khởi tạo lại.

## Kiểm tra

Frontend: `npm test` và `npm run build`. Backend (từ thư mục `backend`): `python -m unittest discover -s tests -v`. Cần test API nghiệp vụ/E2E lại khi tích hợp các màn hình bán hàng với backend.


## Authentication session configuration

Backend authentication uses 15-minute HS256 access tokens and rotating refresh tokens stored as hashes in `auth_sessions`. Refresh tokens are sent only in an `HttpOnly`, `SameSite=Lax` cookie. The login checkbox keeps that cookie for 30 days; without it, the browser receives a session cookie and the server session expires after 12 hours.

Add these values to `backend/.env`:

- `DKAT_AUTH_SECRET_KEY`: a private random value of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and keep it out of source control.
- `DKAT_COOKIE_SECURE=auto`: enables the `Secure` cookie flag when the request is HTTPS or has `X-Forwarded-Proto: https`. Set it to `true` when the HTTPS proxy does not forward that header. Use `false` only for local HTTP development.
- `DKAT_CORS_ORIGINS`: comma-separated frontend origins when the browser calls FastAPI directly. The Vite proxy already keeps local frontend API requests same-origin.

Authentication endpoints are `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`. Refresh rotates and revokes the previous refresh token. Logout revokes the current session. No database migration is needed; the existing `auth_sessions` table stores the refresh-token hash and expiration.

For backend tests, install `backend/requirements-dev.txt` (it includes Starlette's `httpx2` TestClient dependency), then run `python -m unittest discover -s tests -v` from `backend/`.

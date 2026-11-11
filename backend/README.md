# Backend DKat

1. Khởi tạo database từ 01_schema.sql nếu chưa có schema.
2. Trong Workbench, chạy samples/02_auth_schema.sql bằng tài khoản quản trị. Script thêm auth_sessions, store_subscriptions và cấp quyền cho dkat_app. Script lấy kiểu ID từ schema hiện có để hỗ trợ BIGINT hoặc BIGINT UNSIGNED.
3. Điền DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD trong .env. Đặt DKAT_ADMIN_TOKEN bằng một chuỗi ngẫu nhiên riêng có ít nhất 32 ký tự nếu cần tạo cửa hàng/tài khoản mới qua API quản trị.
4. Từ thư mục backend, chạy môi trường ảo và mở Swagger.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở http://127.0.0.1:8000/docs.

5. Nếu đã có tài khoản hợp lệ do Tuấn tạo trên cùng database, đăng nhập bằng POST /api/v1/auth/login. Nếu chưa có, gọi POST /api/v1/admin/accounts với header X-Admin-Token bằng DKAT_ADMIN_TOKEN để tạo cửa hàng, gói đăng ký và OWNER. Payload mẫu:

```json
{
  "shop_name": "Cửa hàng thử nghiệm",
  "plan": "pro",
  "subscription_months": 12,
  "owner_username": "dienowner",
  "owner_full_name": "Võ Thanh Điền",
  "owner_password": "THAY_BANG_MAT_KHAU_RIENG"
}
```

6. Gọi POST /api/v1/auth/login với username và password. Sao chép access_token vào Authorize trong Swagger. Ô Value của HTTPBearer nhận riêng chuỗi token.
7. Thử /categories và /products. Mỗi request lấy user_id, store_id và role từ tài khoản của token. OWNER được ghi, MANAGER/EMPLOYEE chỉ đọc. Đăng nhập quản lý bằng username:manager, nhân viên bằng username:staff theo quy ước của Tuấn. OWNER có thể tạo hai vai trò này qua POST /api/v1/users.
8. Gọi POST /api/v1/auth/logout rồi thử lại API danh mục để xác nhận 401.

DKAT_DEV_USER_ID và DKAT_DEV_STORE_ID đã hết tác dụng. Các tài khoản seed cũ dùng password_hash='!' không đăng nhập được. Cửa hàng phải có gói đăng ký còn hiệu lực, đúng theo Auth của Tuấn. Dữ liệu MySQL và SQLite trong bản clone là hai database riêng.

Các API Auth giữ prefix /api/v1. API danh mục và sản phẩm giữ /categories và /products để bảo toàn URL đã bàn giao.

Postman collection nằm trong samples. Điền biến accessToken bằng token sau đăng nhập. Kiểm thử:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Các test dùng SQLite trong bộ nhớ. Khóa SELECT FOR UPDATE được giả lập trong test danh mục/sản phẩm. Cần kiểm tra migration, quyền MySQL và thao tác đồng thời trên MySQL đích.

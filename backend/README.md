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

## Thử API biến thể và thuộc tính PBI 56

1. Nếu backend dùng tài khoản MySQL `dkat_app`, chạy các lệnh sau trong Workbench bằng kết nối quản trị. Quyền đọc schema và quyền khóa dòng `stores` dùng lại từ phần thiết lập backend.

   ```sql
   GRANT INSERT ON dkat.attributes TO 'dkat_app'@'127.0.0.1';
   GRANT INSERT, UPDATE ON dkat.product_variants TO 'dkat_app'@'127.0.0.1';
   GRANT INSERT, DELETE ON dkat.variant_attribute_values TO 'dkat_app'@'127.0.0.1';
   GRANT INSERT ON dkat.inventory TO 'dkat_app'@'127.0.0.1';
   ```

2. Đăng nhập OWNER. Import `samples/variant.postman_collection.json`, điền `accessToken` và `productId` của sản phẩm thuộc cửa hàng đó, rồi chạy thư mục Variant. Bạn cũng có thể dùng Swagger. OWNER được tạo thuộc tính và ghi biến thể. MANAGER và EMPLOYEE xem thuộc tính và chi tiết sản phẩm trong cửa hàng của mình.
3. Sau request tạo biến thể, lấy `variant_id` trả về và kiểm tra tồn kho khi cửa hàng có chi nhánh ACTIVE.

   ```sql
   SELECT b.branch_id, b.branch_code, i.quantity
   FROM dkat.inventory AS i
   JOIN dkat.branches AS b ON b.branch_id = i.branch_id
   WHERE i.variant_id = 123; -- Thay 123 bằng variant_id vừa tạo.
   ```

Mỗi chi nhánh ACTIVE thuộc cửa hàng có một dòng với `quantity = 0`. POST nhận `sku` nhập tay. PUT giữ SKU cũ nếu bỏ qua `sku` và thay toàn bộ danh sách thuộc tính theo `attributes`. Gửi `[]` hoặc bỏ qua `attributes` để xóa các giá trị cũ. TEXT nhận chuỗi có nội dung, NUMBER nhận số hoặc chuỗi số, BOOLEAN nhận boolean hoặc chuỗi true/false. SKU trùng trả HTTP 409 với `{"detail":"DUPLICATE_SKU"}`.

## Nhập và xuất kho PBI 74 và 75

1. Với database đã tạo từ schema cũ, chạy `database/02_inventory_export.sql` bằng tài khoản quản trị. Với database mới, chạy `database/01_schema.sql`.
2. Nếu dùng tài khoản MySQL local `dkat_app` đã có quyền SELECT, cấp thêm:

   ```sql
   GRANT INSERT, UPDATE ON dkat.inventory TO 'dkat_app'@'127.0.0.1';
   GRANT INSERT ON dkat.inventory_movements TO 'dkat_app'@'127.0.0.1';
   ```

3. Đăng nhập OWNER hoặc MANAGER được phân công chi nhánh. EMPLOYEE cần thêm `ALLOW_EMPLOYEE_STOCK=true` trong `.env` và phải thuộc chi nhánh đó. Khởi động lại backend sau khi sửa `.env`.
4. Trong Swagger, gửi `POST /inventory/import` với `{"branchId":1,"note":"Nhập hàng","items":[{"variantId":1,"quantity":10}]}`. Thay ID theo database của bạn. Gọi `POST /inventory/export` với cùng cấu trúc, thêm `"reason":"HU_HONG"` và nhập số lượng cần xuất. Lý do hỗ trợ `HU_HONG`, `MAU` và `KHAC`.

Mỗi request nhận từ 1 đến 100 biến thể khác nhau, số lượng từng dòng là số nguyên dương. HTTP 201 trả số lượng trước, lượng thay đổi, số lượng sau và ID biến động. Nếu xuất vượt tồn khả dụng ở bất kỳ dòng nào, API trả HTTP 409 `INSUFFICIENT_STOCK` kèm các dòng thiếu và rollback cả lô. API nhập gọi hook phân bổ sau commit. Hook đang chờ triển khai FIFO ở PBI 129/130.

Để chạy nhanh cả hai luồng trên database kiểm thử, import `samples/pbi74-75-stock.postman_collection.json` và điền `accessToken`, `branchId` và `variantId`. Collection thay đổi số lượng tồn và tạo biến động.

## Kiểm kê tồn kho PBI 82

Gọi `POST /inventory/stocktake` với token của OWNER hoặc MANAGER được phân công chi nhánh. EMPLOYEE cần được phân công và có `ALLOW_EMPLOYEE_STOCK=true`. Backend dùng schema và quyền MySQL đã thiết lập cho PBI 74 và 75.

```json
{"branchId": 1, "note": "Kiểm kê cuối ngày", "items": [{"variantId": 1, "countedQuantity": 8}]}
```

Thay ID bằng chi nhánh và biến thể cần kiểm kê. Ghi chú bắt buộc và số đếm phải là số nguyên không âm. Phản hồi HTTP 201 có số trước, chênh lệch và số sau theo từng biến thể. Dòng có chênh lệch ghi biến động `ADJUSTMENT`. Nếu số đếm bằng tồn thực, dòng trả `quantityChange: 0` và `movementId: null`. Nếu số đếm thấp hơn lượng giữ chỗ, API trả HTTP 409 `STOCK_BELOW_RESERVED` với từng dòng vi phạm và hoàn tác cả lô.

Import `samples/pbi82-stocktake.postman_collection.json` để chạy thử. Dùng một biến thể trên database kiểm thử có cả tồn giữ chỗ và tồn khả dụng từ 1 trở lên. Điền `accessToken`, `branchId` và `variantId`, rồi chạy thư mục Stocktake theo thứ tự.

## Lịch sử biến động kho PBI 83

Gọi `GET /inventory/movements` bằng Bearer token. OWNER xem các chi nhánh trong cửa hàng của mình. MANAGER và EMPLOYEE xem các chi nhánh được phân công. Bỏ `branchId` để xem trong toàn bộ chi nhánh có quyền. Truy cập trực tiếp chi nhánh ngoài quyền trả 403.

Ví dụ `GET /inventory/movements?branchId=1&variantId=1&type=EXPORT&from=2026-11-01&to=2026-11-17&page=1&size=20`. Bộ lọc ngày dùng giờ Việt Nam và bao gồm cả ngày `to`. Nếu gửi timestamp ISO 8601, hai đầu mút đều bao gồm và timestamp thiếu múi giờ được hiểu là UTC. Khoảng sai trả 422. Phản hồi trả `createdAt` theo UTC, mới nhất trước. Các biến động cùng thời điểm sắp theo ID giảm dần. Mặc định 50 dòng mỗi trang, tối đa 100.

Với database đã khởi tạo, chạy `database/03_inventory_movement_history.sql` để bổ sung index theo thời gian. File `database/01_schema.sql` đã có index cho database mới.

Để thử cả luồng, import `samples/pbi83-movement-history.postman_collection.json`. Dùng database kiểm thử, điền `accessToken` của OWNER và ID chi nhánh, biến thể đã có dòng tồn kho. Chạy đúng thứ tự để tạo và xác minh ba biến động nhập, xuất và kiểm kê.

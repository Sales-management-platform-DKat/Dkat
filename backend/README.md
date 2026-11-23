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

## Tạo đơn POS PBI 90

Với database đã khởi tạo, chạy `database/04_sales_order_customers.sql`. Database mới dùng `database/01_schema.sql`. Tài khoản backend cần quyền SELECT hiện có và INSERT trên `sales_orders` và `sales_order_items`.

Đăng nhập và gọi `POST /sales-orders` với ID chi nhánh được phép thao tác và hai biến thể còn hàng:

```json
{
  "branchId": 1,
  "discountAmount": "5000.00",
  "items": [{"variantId": 1, "quantity": 2}, {"variantId": 2, "quantity": 1}]
}
```

Bỏ `customerId` hoặc gửi `null` cho khách vãng lai. Với khách có hồ sơ, gửi ID khách thuộc cùng cửa hàng. API lấy giá từ database, lưu tên, SKU và giá trên từng dòng đơn, rồi trả HTTP 201 với trạng thái `PENDING`. Mã đơn dùng ngày Việt Nam và hậu tố UUID. Số tiền trả dưới dạng chuỗi thập phân. Khi thiếu hàng, API trả `409` với `detail.code = "OUT_OF_STOCK"` và `detail.items` chứa `variantId` và `available`. Kho và số lượng giữ chỗ giữ nguyên. Luồng thanh toán cần kiểm tra lại tồn khi chốt đơn.

Để thử qua Postman trên database kiểm thử, import `samples/pbi90-sales-order.postman_collection.json`, điền `accessToken`, `branchId`, `variantIdA` và `variantIdB`, rồi chạy thư mục SalesOrder theo thứ tự.

## Danh sách, chi tiết và hủy đơn PBI 91

Với database hiện có, chạy `database/05_sales_order_cancellation.sql` để thêm thời điểm và lý do hủy. Tài khoản backend cần SELECT và UPDATE trên sales_orders, cùng quyền đọc các bảng liên quan.

- `GET /sales-orders?branchId=1&status=PENDING&keyword=DK-&page=1&size=20` trả các đơn theo quyền chi nhánh, mới nhất trước. Có thêm bộ lọc customerId, from và to. Ngày YYYY-MM-DD dùng giờ Việt Nam và bao gồm ngày cuối. Timestamp ISO dùng múi giờ được gửi, mặc định UTC khi thiếu múi giờ.
- `GET /sales-orders/{id}` trả dòng hàng snapshot, lịch sử thanh toán, tên khách hoặc null, và người tạo. paymentMethods trong danh sách là các phương thức đã thanh toán SUCCESS.
- `POST /sales-orders/{id}/cancel` nhận `{"reason":"Khách đổi ý"}` và trả HTTP 200 với trạng thái CANCELLED. Lý do là bắt buộc. Đơn không còn PENDING trả 409 ORDER_NOT_PENDING. Hai request hủy cùng đơn được tuần tự hóa bằng khóa dòng. Cả xem và hủy đều giới hạn trong chi nhánh có quyền.

Import `samples/pbi91-sales-orders.postman_collection.json`. Điền accessToken, branchId, variantId còn hàng và paidOrderId của đơn PAID để chạy đầy đủ các ca.

## Xác nhận thanh toán POS PBI 99

1. Database mới chạy `database/01_schema.sql`. Database cũ cần các migration 02–05 đã liệt kê ở trên. PBI 99 không thêm bảng/cột. Tài khoản backend cần SELECT trên các bảng liên quan, UPDATE trên `sales_orders` và `inventory`, INSERT trên `payments` và `inventory_movements`.
2. Đăng nhập OWNER, MANAGER hoặc EMPLOYEE có quyền tại chi nhánh của đơn. Trong Swagger gọi `POST /sales-orders/{order_id}/confirm-payment`:

   ```json
   {"paymentMethod": "CASH", "amount": "99000.00"}
   ```

   Thay ID và số tiền bằng `salesOrderId`, `totalAmount` vừa trả từ API tạo đơn. Phương thức nhận CASH, BANK_TRANSFER, CARD hoặc OTHER. `amount` là tiền thanh toán cho đơn; với tiền mặt, frontend tự tính tiền khách đưa và tiền thừa. Tổng bằng 0 vẫn được ghi nhận khi đơn giảm giá toàn bộ.
3. HTTP 200 trả chi tiết đơn PAID, thời điểm thanh toán và một payment SUCCESS. Tồn kho giảm theo dòng hàng snapshot; movement SALE có `referenceType: SALES_ORDER`, `referenceId` là ID đơn. Thanh toán, tồn kho, movement và trạng thái đơn cùng commit hoặc cùng rollback.

Số tiền không khớp trả 422 `PAYMENT_AMOUNT_MISMATCH`. Tồn khả dụng không đủ trả 409 `OUT_OF_STOCK` với chi tiết từng biến thể; hàng giữ chỗ cho preorder được bảo vệ. Đơn đã PAID/CANCELLED trả 409 `ORDER_NOT_PENDING`. Ngoài cửa hàng trả 404; ngoài chi nhánh được phân công trả 403. Lỗi database trả 503 và hoàn tác giao dịch. Gửi lại cùng đơn sau khi kết nối bị ngắt sẽ không trừ kho lần thứ hai; đọc GET chi tiết để kiểm tra trạng thái.

Thử nhanh: import `samples/pbi99-confirm-payment.postman_collection.json`, điền `accessToken`, `branchId`, `variantId` còn hàng, rồi chạy thư mục SalesPayment trên database kiểm thử. Collection tạo và thanh toán một đơn thật.

Chạy bộ kiểm thử MySQL riêng bằng PowerShell từ thư mục backend:

```powershell
.\scripts\test_pbi99_mysql.ps1
```

Cần MySQL Server 8.0 và môi trường `.venv` đã cài `requirements-dev.txt`. Nếu MySQL nằm ở chỗ khác, thêm `-MySqlBin 'D:\MySQL\bin'`. Script tạo một MySQL tạm tại máy, nạp schema riêng `dkat_pbi99_test`, chạy các ca thanh toán, phân quyền, giữ chỗ, yêu cầu đồng thời và lỗi SQL ở ba giai đoạn, rồi tắt server. Database trong `.env` không được dùng. Log tạm được giữ tại đường dẫn cuối kết quả.

## Tạo đơn đặt trước PBI 110

1. Database mới chạy `database/01_schema.sql`. Database cũ chạy migration `database/06_public_preorders.sql` sau migration 04. API dùng thêm ba cột `preorders.customer_id`, `customer_address`, `note` và bảng `preorder_request_limits`. Tài khoản backend cần SELECT các bảng liên quan, INSERT/UPDATE trên `customers` và `preorder_request_limits`, INSERT trên `preorders` và `preorder_items`; quyền khóa inventory dùng lại từ các API kho.
2. Khởi động backend, mở Swagger và gọi `POST /preorders` trong nhóm `preorders-public`. API công khai, không cần token:

   ```json
   {
     "branchId": 1,
     "customer": {
       "fullName": "Nguyễn Văn An",
       "phone": "0901234567",
       "email": "an@example.com",
       "address": "123 Nguyễn Trãi, TP.HCM"
     },
     "items": [{"variantId": 1, "quantity": 2}],
     "note": "Gọi trước khi giao"
   }
   ```

   Thay ID bằng dữ liệu thực. Từng dòng phải có tồn khả dụng nhỏ hơn lượng yêu cầu; chỉ một dòng còn đủ hàng cũng khiến cả đơn bị từ chối. `email` và `note` có thể bỏ qua. Điện thoại nhận số Việt Nam 10–11 chữ số bắt đầu bằng 0, hoặc dạng +84/84 tương ứng, có thể có khoảng trắng, dấu chấm, gạch ngang hoặc ngoặc; được chuẩn hóa về dạng bắt đầu bằng 0. Tối đa 100 biến thể khác nhau, số lượng nguyên dương.
3. Thành công trả 201 với `preorderId`, `preorderCode`, `customerId`, tổng tiền, các dòng snapshot và trạng thái WAITING_STOCK / UNPAID. Kho, giữ chỗ và thanh toán giữ nguyên. Hàm dùng chung `app/modules/customers/service.py::upsert_customer_by_phone` tìm/tạo hồ sơ bằng `(store_id, phone)` trong cùng transaction; không ghi đè hồ sơ cũ từ dữ liệu công khai. Mỗi đơn giữ riêng tên, điện thoại, email và địa chỉ khách lúc đặt. Mã đơn dùng ngày Việt Nam và UUID để tránh trùng giữa các worker.

Lỗi trả trực tiếp `{code, message, details:[{field, reason}]}`, không bọc `detail`. Thiếu/sai dữ liệu trả 422 INVALID_PREORDER và không tạo hồ sơ khách hay đơn. Còn đủ hàng trả 409 VARIANT_IN_STOCK; sản phẩm ngừng hoạt động trả 409 VARIANT_INACTIVE; chi nhánh hoặc biến thể không hợp lệ trả 404. Lỗi SQL trả 503 và rollback cả hồ sơ khách mới, đơn và dòng hàng.

Giới hạn **5 yêu cầu/10 phút/IP theo cửa sổ trượt**, lưu trong database để dùng chung nhiều worker. Lần tiếp theo trả 429 RATE_LIMIT_EXCEEDED kèm Retry-After. Yêu cầu bị lỗi JSON, dữ liệu hoặc nghiệp vụ vẫn được tính. Địa chỉ IP lấy từ ASGI client; không tự tin header X-Forwarded-For. Khi đặt sau reverse proxy, cấu hình Uvicorn chỉ tin IP proxy thực tế (`--forwarded-allow-ips`); không đặt `*` cho máy chủ truy cập trực tiếp. Có thể định kỳ xóa các dòng limiter có `updated_at` cũ hơn một ngày bằng tài khoản vận hành.

Thử qua Postman: import `samples/pbi110-public-preorders.postman_collection.json`, điền `accessToken` để đọc kho, `branchId`, `variantId` có available < 2 và `inStockVariantId` có available >= 1. Chạy thư mục Preorder từ IP chưa gửi yêu cầu trong 10 phút. Collection tạo hai đơn thật và kiểm tra lần thứ sáu bị giới hạn; token không được gửi vào API tạo đặt trước.

Chạy test tự động trên MySQL riêng từ thư mục backend:

```powershell
.\scripts\test_pbi110_mysql.ps1
```

Script khởi tạo database tạm, kiểm tra migration chạy lại, kiểm thử tạo đơn, snapshot, validation, phạm vi cửa hàng, khách trùng số điện thoại, nhiều request đồng thời, giới hạn IP và lỗi SQL giữa chừng. Không kết nối database trong `.env`.

## Import CSV sản phẩm và biến thể PBI 111

1. Cài lại `pip install -r requirements.txt` để có `python-multipart`, rồi khởi động backend. PBI này không thêm bảng hay migration. Tài khoản database dùng quyền đọc và các quyền tạo danh mục, sản phẩm, thuộc tính, biến thể, giá trị thuộc tính và tồn kho của PBI 38/39/56; quyền khóa stores dùng lại từ các API danh mục.
2. Đăng nhập OWNER và Authorize trong Swagger. Mở `POST /products/import-csv`, chọn file `data/sample-products.csv` và giữ `dryRun=true` để kiểm tra trước. File mẫu có 20 biến thể thuộc 5 sản phẩm.
3. Preview trả HTTP 200 với `valid`, `totalRows`, `validRows`, `errors` và `summary` (số danh mục/sản phẩm/biến thể/thuộc tính sẽ tạo khi hợp lệ). Preview không ghi dữ liệu. Sửa lỗi theo `errors[].line` và `field`; dòng tiêu đề là 1. Với ô có xuống dòng, số dòng là dòng vật lý bắt đầu bản ghi trong file.
4. Đặt `dryRun=false` và gửi lại để import thật. Thành công trả 201 kèm ID sản phẩm/biến thể theo dòng CSV. File sai trả 422, `detail.code=INVALID_PRODUCT_CSV` và `detail.errors`. Nếu bất kỳ dòng nào sai hoặc ghi SQL thất bại, không giữ lại danh mục, sản phẩm, thuộc tính, biến thể hoặc tồn kho được tạo từ file đó.

CSV phân cách bằng dấu phẩy, UTF-8 (chấp nhận BOM), tối đa 500 dòng dữ liệu và 5 MiB. Các cột bắt buộc: `product_name,category,variant_name,sku,price,cost_price,attributes`; được để trống giá vốn và thuộc tính. Giá không âm, tối đa 2 số thập phân, dùng dấu chấm; thuộc tính dùng `Size:M;Màu:Đen`. Dòng trống hoàn toàn được bỏ qua.

Cùng danh mục và tên sản phẩm được gom thành nhiều biến thể. Danh mục/thuộc tính chưa có được tạo mới (danh mục gốc, thuộc tính TEXT). Tên đã có được tìm trong cửa hàng của OWNER; tên trùng gây mơ hồ hoặc đối tượng INACTIVE bị từ chối. Thuộc tính NUMBER/BOOLEAN đã có dùng cùng bộ kiểm tra giá trị của API biến thể. Việc so tên/SKU theo đúng collation của cột database, gồm quy tắc chữ hoa và dấu. SKU đã tồn tại hoặc trùng trong file bị từ chối; import không cập nhật hay ghi đè SKU cũ. Sản phẩm mới nhận mã `CSV-<UUID>`. Mỗi biến thể mới có tồn 0 tại các chi nhánh ACTIVE, không có movement nhập kho.

Kiểm thử: import `samples/pbi111-product-csv.postman_collection.json`, điền `accessToken` của OWNER và đặt thư mục làm việc Postman/Newman là thư mục gốc dự án để đọc `data/*.csv`. Dùng database kiểm thử chưa import các SKU mẫu. Bộ test MySQL riêng chạy bằng `.\scripts\test_pbi111_mysql.ps1` từ backend; có cả import thật 500 dòng, rollback SQL và hai yêu cầu đồng thời cùng SKU.

## Thanh toán, danh sách và chi tiết đặt trước PBI 121

1. Dùng schema mới hoặc migration 06 của PBI 110. Không có migration mới cho PBI 121. Tài khoản backend cần SELECT các bảng liên quan, UPDATE trên `preorders` và INSERT trên `payments`.
2. Đăng nhập OWNER, MANAGER hoặc EMPLOYEE và Authorize. OWNER thao tác các chi nhánh trong cửa hàng; hai vai trò còn lại cần được phân công chi nhánh.
3. Gọi `GET /preorders?branchId=1&status=WAITING_STOCK&paymentStatus=UNPAID&keyword=PD-&page=1&size=20`. Các bộ lọc đều tùy chọn. Keyword tìm theo mã, tên hoặc điện thoại snapshot (hỗ trợ số +84 đầy đủ). Mặc định 50 dòng, tối đa 100; cũ nhất trước, cùng thời điểm thì ID tăng dần. Mỗi đơn có khách, số tiền, trạng thái và dòng hàng kèm quantity/allocatedQuantity.
4. Gọi `GET /preorders/{preorder_id}` để xem thêm toàn bộ lịch sử thanh toán, `fulfillment` (null khi chưa có), và `notifications` mới nhất trước. Tên, giá, SKU và thông tin khách lấy từ snapshot lúc đặt; thời gian trả theo UTC.
5. Gọi `POST /preorders/{preorder_id}/confirm-payment` với `{"paymentMethod":"CASH","amount":"99000.00"}`; thay số tiền bằng đúng totalAmount của đơn. Hỗ trợ CASH, BANK_TRANSFER, CARD, OTHER. Thành công trả 200 với paymentStatus PAID, một payment SUCCESS, confirmedBy và confirmedAt. Đây là ghi nhận thủ công sau khi kiểm tra thanh toán bên ngoài; API không gọi ngân hàng.

Chỉ đơn WAITING_STOCK/READY/NOTIFIED còn UNPAID được thanh toán; tổng bằng 0 vẫn được ghi nhận. Số tiền sai trả 422 PAYMENT_AMOUNT_MISMATCH; đơn không hợp lệ trả 409 PREORDER_NOT_PAYABLE; đã thanh toán/hoàn tiền hoặc đã có SUCCESS trả 409 PREORDER_ALREADY_PAID. Khóa dòng đơn chống ghi hai lần. Lỗi SQL trả 503 và rollback payment cùng payment_status. Trạng thái xử lý đơn, inventory, lượng phân bổ và movement giữ nguyên.

Ngoài cửa hàng trả 404 PREORDER_NOT_FOUND, ngoài chi nhánh có quyền trả 403; danh sách tự giới hạn theo quyền. Ba API này cần token và không dùng limiter của API tạo đơn công khai.

Thử nhanh: import `samples/pbi121-preorder-admin.postman_collection.json`, điền `accessToken` và `preorderId` của đơn UNPAID trên database kiểm thử, rồi chạy thư mục PreorderAdmin. Collection đọc kho trước/sau, thanh toán và thử gọi lặp. Chạy bộ test MySQL riêng bằng `.\scripts\test_pbi121_mysql.ps1` từ backend để kiểm tra thêm phân quyền, FIFO, dữ liệu cũ, thông báo, rollback và thanh toán đồng thời.

## Hoàn đơn bán đã thanh toán PBI 122

1. Dùng schema mới hoặc migration 05 (`sales_orders.cancel_reason`, `cancelled_at`) và schema kho của PBI 74/75. PBI 122 không thêm migration. Tài khoản backend cần SELECT, UPDATE trên sales_orders/payments, INSERT/UPDATE trên inventory và INSERT trên inventory_movements; quyền khóa dòng dùng lại từ API thanh toán.
2. Đăng nhập OWNER hoặc MANAGER được phân công chi nhánh. Trong Swagger gọi `POST /sales-orders/{order_id}/refund` với `{"reason":"Khách trả toàn bộ hàng"}`. Lý do được cắt khoảng trắng đầu/cuối, bắt buộc có nội dung và tối đa 255 ký tự. API hoàn toàn bộ đơn; gửi thêm amount/items bị từ chối.
3. HTTP 200 trả đơn CANCELLED, cancelReason/cancelledAt và các payment SUCCESS đã thành REFUNDED. paidAt, dòng hàng, ID thanh toán, phương thức, số tiền và thông tin xác nhận ban đầu được giữ lại. Lịch sử FAILED/PENDING giữ nguyên. Đây là ghi nhận hoàn trong hệ thống; cửa hàng thực hiện hoàn tiền cho khách bên ngoài.

Trong cùng transaction: khóa đơn và inventory theo variant_id tăng dần, cập nhật thanh toán, cộng đúng lượng đã bán về chi nhánh gốc, ghi ADJUSTMENT dương với note `Hoàn đơn <mã>`, referenceType SALES_ORDER, referenceId và createdBy của người hoàn, rồi cập nhật trạng thái/lý do/thời điểm. Không xóa dòng đơn hay thanh toán. Đơn CANCELLED và payment REFUNDED được loại khỏi phép tính doanh thu theo trạng thái PAID/SUCCESS.

PENDING, CANCELLED hoặc hoàn lần hai trả 409 ORDER_NOT_PAID. Lịch sử thanh toán thiếu SUCCESS, đã có REFUNDED hoặc tổng SUCCESS khác totalAmount trả 409 ORDER_PAYMENT_INCONSISTENT để kiểm tra lại dữ liệu. Kho vượt giới hạn INT trả 409 STOCK_LIMIT_EXCEEDED và hoàn tác cả đơn. SQL lỗi trả 503 và rollback thanh toán, kho, movement, trạng thái đơn. Đơn có biến thể ngừng hoạt động vẫn hoàn theo snapshot; inventory cũ bị thiếu được tạo ở mức 0 rồi cộng lượng trả. Lượng giữ chỗ preorder giữ nguyên. EMPLOYEE trả 403; MANAGER ngoài chi nhánh trả 403; ngoài cửa hàng trả 404.

Thử nhanh trên database kiểm thử: import `samples/pbi122-sales-refund.postman_collection.json`, điền accessToken OWNER/MANAGER và orderId của đơn PAID hợp lệ rồi chạy SalesRefund theo thứ tự. Collection kiểm tra kho trước/sau, movement, lịch sử và việc hoàn lần hai bị chặn. Chạy `.\scripts\test_pbi122_mysql.ps1` từ backend để kiểm tra thêm phân quyền, các phương thức thanh toán, dữ liệu cũ, rollback SQL, tràn kho và yêu cầu đồng thời.

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
- `/#/login`: form đăng nhập dành cho cửa hàng đã đăng ký DKat; cần kết nối backend xác thực.
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

## Phân chia mã nguồn

- `src/main.jsx`: màn hình, reusable UI và dialog. Các feature nằm trong các hàm có tên để nhóm dễ tách ra thư mục features sau khi chốt UI.
- `src/styles.css`: design tokens sáng/tối, landing, admin và responsive.
- `src/domain.js`: mô phỏng nghiệp vụ kho, POS, FIFO và báo cáo.
- `src/seed.js`: dữ liệu giả. localStorage key: dkat-demo-v1.
- `src/csv.js`: CSV UTF-8, tối đa 100 dòng, validate toàn file trước khi lưu.
- `src/api.js`: HTTP adapter để nhóm tiếp tục nối FastAPI; chưa được gọi thay cho mock trong bản này.
- `tests/domain.test.js`: kiểm thử logic trọng yếu bằng Node test runner.

## Giới hạn cần biết trước khi nối backend

- Backend xác thực chưa được kết nối. Form đăng nhập cửa hàng chỉ là giao diện; bản demo vào thẳng quản trị và phân quyền chỉ mô phỏng trên trình duyệt.
- Không gửi SMS/email hoặc xác minh ngân hàng, không hỗ trợ thao tác nhiều nhân viên đồng thời. Chống tranh chấp phải triển khai ở backend transaction.
- Link preorder chỉ hoạt động trên trình duyệt đã tạo dữ liệu demo. Token thật phải lưu hash và được xác minh tại server.
- UI sản phẩm hiển thị biến thể theo từng dòng SKU; backend cần nối products/product_variants/attributes thay cho danh sách phẳng này.
- Báo cáo số tiền tính từ dữ liệu demo; biểu đồ trang landing và Dashboard ghi rõ minh họa. Báo cáo có bộ lọc thời gian tương đối, chưa có tổng hợp lịch theo tuần/tháng/năm.
- Font Manrope tải Google Fonts khi có mạng, tự dùng Segoe UI nếu offline. Biểu tượng và minh họa sản phẩm đều SVG/CSS, không phụ thuộc ảnh bên ngoài.
- Không có catalog/checkout công khai, trả hàng POS, cổng thanh toán, vận chuyển tích hợp, đa kênh hay chuyển kho.
- Dữ liệu localStorage không phù hợp lưu thông tin khách thật. Dùng dữ liệu giả khi thử. Có thể xóa key dkat-demo-v1 trong DevTools để khởi tạo lại.

## Kiểm tra

`npm test` và `npm run build`. Đã kiểm tra trình duyệt landing, login, Dashboard và POS trong môi trường phát triển. Cần test API/E2E lại khi tích hợp backend thật.

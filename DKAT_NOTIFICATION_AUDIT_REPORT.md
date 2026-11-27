# Báo cáo rà soát thông báo – DKat (27/11/2026)

Phạm vi: frontend (`frontend/src`), cùng lỗi màn hình Đặt trước và Khách hàng. Không đổi backend API, database hay schema.

## 1. Số liệu rà soát

| Hạng mục | Số lượng |
|---|---|
| File frontend đang dùng được quét | 63 |
| Chuỗi tiếng Việt trong các file đó | 1.881 |
| Lời gọi thông báo (`notify.*`, `confirmAction`, `setError`/`setNotice`, `pushToast`) | 97 |
| Thông báo lỗi trong `lib/api-errors.js` | 40+ (đều đã có bản tiếng Anh) |
| Chuỗi tiếng Việt trong backend | 236, trong đó 195 chưa có bản tiếng Anh. Khoảng 95 chuỗi hiện ra giao diện, phần còn lại là nội dung SMS/email gửi khách hoặc log của nhà cung cấp. |

Các màn hình đã gọi `t()` gần như đầy đủ. Lỗi chủ yếu nằm ở **tầng hiển thị dùng chung** và **thông báo từ API**.

## 2. Vấn đề phát hiện và cách xử lý

### Lỗi nghiêm trọng
1. **Báo thành công giả khi gửi lại thông báo đặt trước.** `POST /notifications/{id}/resend` trả HTTP 200 kèm `result: "FAILED"` khi gửi lại vẫn lỗi, nhưng UI luôn báo "Đã gửi lại thông báo". Giờ UI kiểm tra `result` và hiện lý do lỗi.
2. **Báo thành công giả khi thêm khách hàng trùng số điện thoại.** Backend trả về khách đã có và không tạo mới, nhưng UI báo "Đã lưu khách hàng". Giờ UI báo dạng cảnh báo: "Số điện thoại … đã thuộc về khách hàng …. Không tạo khách hàng mới".
3. **Mỗi lần xác nhận mở hai dialog chồng nhau.** `main.jsx` mount cả `components/confirm.jsx` (bản cũ) lẫn overlay `ConfirmHost`, và cả hai cùng nghe sự kiện `dkat-confirm`. Giờ chỉ còn một host. `components/confirm.jsx` chỉ còn re-export.
4. **ConfirmDialog giữ lại lý do đã gõ** từ lần xác nhận trước. Giờ mỗi yêu cầu có key riêng nên bắt đầu trống. Ô lý do được giới hạn 255 ký tự (khớp backend) và bị khóa khi đang xử lý.

### Trộn ngôn ngữ
5. Toast, ConfirmDialog, FormDialog/FormField, ErrorState **không dịch lúc render**. Tiêu đề toast mặc định, nút "Xác nhận/Hủy/Đang xử lý…/Đang lưu…", lỗi validation và mọi thông báo lỗi API luôn hiện tiếng Việt trong giao diện tiếng Anh. Giờ các component này giữ chuỗi gốc (hoặc khóa `{key, values}`) và dịch khi render, nên thông báo đang mở cũng đổi theo khi chuyển ngôn ngữ.
6. Thông báo backend **có tham số** (mã chi nhánh trùng, tên đăng nhập trùng, lỗi từng dòng CSV, chi nhánh còn đơn đặt trước…) không tra được trong catalog. Đã thêm `DYNAMIC_MESSAGES` vào `i18n/index.js` (15 mẫu), ánh xạ sang khóa `api.message.*` có ở cả hai ngôn ngữ.
7. Đã thêm bản tiếng Anh cho khoảng 60 thông báo tĩnh của backend hiện ra UI (phiên đăng nhập, mật khẩu, phân quyền nhân viên, CSV/Excel, ảnh sản phẩm…).
8. Lỗi từng dòng và lỗi file trong hộp thoại nhập kho CSV giờ được dịch khi render.

### Nội dung chưa rõ hoặc sai ngữ cảnh
9. `errorMessage()` thay lý do cụ thể từ API bằng câu chung ("Không lưu được…") nếu câu đó chưa có trong catalog. Giờ hàm giữ lại lý do của `ApiError` (vốn đã được làm sạch), chỉ dùng câu chung khi không biết nguyên nhân.
10. Lịch sử thông báo đặt trước hiện mã thô (`NOT_CONFIGURED`, `TIMEOUT`…). Giờ hiện lý do kèm hướng xử lý (chưa cấu hình nhà cung cấp, sai số điện thoại, hết hạn mức, lỗi kết nối…). Mã gốc vẫn còn trong tooltip cho người cấu hình.
11. Toast của đơn đặt trước ghi rõ mã đơn và hệ quả: "Đã hủy đơn đặt trước PD-… Hàng đang giữ đã được trả lại kho", "Đã ghi nhận thanh toán cho đơn đặt trước PD-…", "Đã xác nhận giao … và trừ tồn kho".
12. Khách hàng: thông báo phân biệt thêm mới và cập nhật, có tên khách. Tooltip ở cột "Số đơn"/"Tổng đã mua" giải thích cách tính (đơn bán đã thanh toán + đơn đặt trước đã giao, trong các chi nhánh được xem). Câu báo lịch sử trống đã sửa cho đúng (lịch sử hiện mọi trạng thái), và bổ sung nhãn `NOTIFIED`/`PENDING` còn thiếu.

## 3. Lỗi màn hình Đặt trước và Khách hàng

- **Backend thật:** đã kiểm thử end-to-end trên MySQL tạm thời có đủ schema `01`–`09`. Tạo đơn → nhập kho → READY → ghi lịch sử SMS/email → thanh toán → giao hàng → khách hàng có `orderCount=1`, `totalSpent=200000`. Toàn bộ chạy đúng. Nếu môi trường thật vẫn lỗi (danh sách đặt trước báo "Không thể kết nối…", lịch sử thông báo lỗi), nguyên nhân khả dĩ nhất là DB chưa chạy các script `database/06`–`09_*.sql`. Các script này an toàn khi chạy lại. Chưa kiểm tra được trên DB production vì không có quyền truy cập.
- **Bản demo** (dùng chung màn hình): thiếu endpoint lịch sử thông báo và gửi lại, không sinh thông báo "hàng đã có" khi nhập kho, không có dữ liệu đặt trước mẫu, số liệu khách hàng bỏ qua đơn đặt trước đã giao và không giới hạn theo chi nhánh. Đã bổ sung đủ. Dữ liệu demo đổi phiên bản (v3), nên trình duyệt đang giữ dữ liệu demo cũ sẽ được tạo lại một lần.

## 4. Kiểm tra song ngữ

- `tests/i18n-coverage.test.js` (công cụ `scripts/check-i18n.mjs`): không còn chuỗi tiếng Việt hardcode và không thiếu bản dịch trong các file được render.
- `tests/notification-messages.test.js` (mới, 7 test): thông báo động hiện đúng ngôn ngữ; mọi thông báo của `api-errors.js` có bản tiếng Anh; lý do lỗi API được giữ lại; mã lỗi nhà cung cấp hiện thành lý do dễ hiểu ở cả hai ngôn ngữ; toast không bị nhân bản; chỉ còn một host xác nhận.
- `tests/system-audit.test.js`: cập nhật kịch bản FIFO, thêm test gửi lại thông báo và tổng chi tiêu của khách hàng.

## 5. Build và test

- `npm test`: **65/65 pass**.
- `npm run build`: **thành công**. Cảnh báo chunk lớn hơn 500 kB đã có từ trước.
- Backend `unittest`: 62/62 pass (không có thay đổi backend).

## 6. UX đã có sẵn và được giữ nguyên

Toast chống trùng trong 4 giây (lặp lại thì tăng bộ đếm ×n), tối đa 4 toast cùng lúc. Thời gian hiển thị theo loại: 4–7 giây, lỗi 5xx/mạng giữ đến khi người dùng đóng. Mọi toast đóng được và dừng đếm khi rê chuột vào. Dialog xác nhận phân biệt `danger`/`warning`/`primary`, chặn bấm nhiều lần khi đang xử lý.

## 7. Chưa xử lý và lý do

- Các câu ghép bằng nhiều mảnh `t()` (ví dụ `${t('Chỉ còn')} ${n} ${t('sản phẩm khả dụng')}`) vẫn hiện đúng ngôn ngữ nhưng trật tự từ tiếng Anh chưa tự nhiên. Muốn sửa cần chuyển từng câu sang khóa có tham số (khoảng 45 chỗ), nên để làm thành một đợt riêng.
- Nội dung SMS/email gửi khách (`backend/.../templates.py`) và log của nhà cung cấp thuộc backend, ngoài phạm vi.
- Backend trả HTTP 503 với câu "Không thể kết nối cơ sở dữ liệu" cả khi lỗi thực ra là thiếu cột. Sửa cần đổi backend, ngoài phạm vi.
- Chưa kiểm tra giao diện trực tiếp trên trình duyệt (phiên làm việc này không có công cụ trình duyệt). Các kiểm tra trên dựa vào test tự động và build.

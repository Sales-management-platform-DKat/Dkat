# Kiểm thử tích hợp vòng 2 và đối chiếu số liệu, 25/11/2026

Mục tiêu: xác nhận các bug đã sửa và dữ liệu nhất quán (NFR-04, NFR-11).

**Kết quả: không còn bug mức Cao đang mở.**

- Bug: [DKat_Bug_Log.xlsx](../../DKat_Bug_Log.xlsx). Tổng 19 bug, 12 đã đóng, 7 còn mở (3 mức Trung bình, 4 mức Thấp).
- Pass/Fail: [DKat_Test_Cases.xlsx](../../DKat_Test_Cases.xlsx).
  - Sheet `POS & Auth`: 12/12 Pass.
  - Sheet `Đặt trước & Thông báo`: 12/12 Pass.
  - Sheet `Test case`: 76 dòng, 70 Pass, 5 Fail (đều thuộc bug còn mở), 1 Chưa test (dòng mẫu cũ TC-PRE-001).
- Bằng chứng: [logs/](logs/), đã che email, SĐT thật và đường dẫn máy.

## 1. Kiểm tra lại từng bug

| Bug | Mức | Phụ trách | Kết quả vòng 2 | Trạng thái |
|---|---|---|---|---|
| BUG-005 thông báo không gửi | Cao | Tuấn | TC-PN-06..09 Đạt; luồng thật: email đến, đơn chuyển NOTIFIED | **Đã đóng** |
| BUG-006 job hết hạn không chạy | Cao | Khang | Tuấn khôi phục `create_task(run_preorder_expiry)` trong `lifespan` (code PBI 140 bị mất ở merge `9cc2512`); `test_api_lifespan_runs_scheduled_expiry` Đạt | **Đã đóng**, nhờ Khang review |
| BUG-007 `LivePos.jsx` gửi sai body | Thấp | Quốc Anh | File vẫn còn, không được import, người dùng không gặp | Còn mở |
| BUG-008 bắt buộc SSL với MySQL local | Cao | Khang | Mọi lượt chạy dùng `DB_SSL_MODE=disabled`; test cấu hình Đạt | **Đã đóng** |
| BUG-009 không có seed cho DB phát triển | Trung bình | Tuấn | `scripts/seed.py` vẫn 0 byte (`demo_reset` chỉ dùng cho DB demo) | Còn mở |
| BUG-010 integration test lệch hợp đồng API | Trung bình | Điền | Bản gốc vẫn đỏ; bản đã chỉnh đạt hết | Còn mở |
| BUG-011 2 unit test báo cáo | Trung bình | Khang | Bản clone sạch vẫn 2 ERROR `no such table: sales_orders` | Còn mở |
| BUG-012 `createdAt` lệch 7 giờ | Thấp | Điền | `createdAt 04:07Z`, `paidAt 21:07Z` | Còn mở |
| BUG-013 README backend lệch | Thấp | Khang | Vẫn ghi `plan: pro`, thiếu `owner_email` | Còn mở |
| BUG-014 dashboard hiện 0 | Trung bình | Khang | Thẻ Tổng quan khớp SQL tay ở 4 phạm vi | **Đã đóng** |
| BUG-015 SMS `DUPLICATE_REQUEST` sau reset | Trung bình | Tuấn | Sau reset SMS báo `TEMPLATE_MISMATCH` (giới hạn tài khoản thử), không còn trùng mã yêu cầu | **Đã đóng** |
| BUG-016 menu Thông báo là bảng mẫu | Thấp | Khang | Vẫn còn | Còn mở |
| BUG-017 giờ gửi lệch 7 giờ | Thấp | Tuấn | `sentAt` / `lastAttemptAt` kèm `Z` | **Đã đóng** |
| BUG-018 gửi lại thành công nhưng đơn vẫn READY | Trung bình | Tuấn | TC-PN-08: đơn chuyển NOTIFIED | **Đã đóng** |
| BUG-019 (mới) test cấu hình DB đỏ khi có `.env` | Thấp | Tuấn | Tìm thấy và sửa trong vòng này: test tự đặt `DB_SSL_MODE`; 9/9 Đạt cả khi có `.env` | **Đã đóng** |

**Lưu ý về BUG-011.** Nếu máy có `backend/.env` trỏ tới MySQL, unit test sẽ chạy trên MySQL và 2 test này lại đạt, dễ tưởng là đã sửa. Hãy kiểm tra trên bản clone không có `.env`.

## 2. Đối chiếu số liệu (`python -m scripts.check_reconciliation`)

Script chỉ đọc dữ liệu, chạy trên DB đang cấu hình trong `.env`. Mỗi lần chạy có 24 phép so:

- **Doanh thu.** `/reports/revenue` theo ngày, tuần, tháng và `/reports/summary` được so với SQL viết tay: đơn bán `PAID` tính theo `paid_at`, cộng đơn đặt trước `FULFILLED` chưa hoàn tiền tính theo `fulfilled_at`, chia ngày theo giờ Việt Nam. So cho toàn cửa hàng và từng chi nhánh trong 30 ngày, gồm tổng tiền, số đơn, tiền từng ngày, phần bán tại quầy so với phần đặt trước, và giá trị trung bình mỗi đơn.
- **Tồn kho.** Với mỗi dòng tồn: `quantity` = tồn đầu (0, vì dòng tồn được tạo rỗng) + tổng biến động.
- **Biến động khớp chứng từ:**
  - Biến động `SALE` = số lượng của các đơn đã thanh toán.
  - Hoàn kho (`ADJUSTMENT` gắn `SALES_ORDER`) = số lượng của các đơn đã hoàn.
  - `PREORDER_FULFILLMENT` = số lượng của các đơn đặt trước đã giao.
- **Hàng đang giữ.** Cột Đã giữ = tổng phân bổ của các đơn đặt trước đang mở; Khả dụng = Tồn thực − Đã giữ; không đơn đã đóng nào còn giữ hàng.

| Trạng thái dữ liệu | Kết quả | Log |
|---|---|---|
| Seed mới (74 đơn trong 29 ngày) | 24/24 khớp | `r2_20_recon_seed.log` |
| Sau 12 test case POS & Auth (thanh toán, hủy, hoàn đơn) | 24/24 khớp. Tồn 157 = biến động 157; bán 215 = 215; hoàn kho 4 = 4 | `r2_42`, `r2_43` |
| Sau 12 test case Đặt trước & Thông báo (FIFO, giao, hủy, hết hạn) | 24/24 khớp. Giao đặt trước −2 = 2; đang giữ 1 = 1; đơn đã đóng còn giữ hàng: 0 | `r2_50`, `r2_51` |
| Sau trọn luồng thật (POS + đặt trước + giao) | 24/24 khớp. CN01: 39.037.000 đ, 55 đơn, khớp SQL | `r2_62`, `r2_63` |

## 3. Ba vai trò với chức năng bị cấm (`python -m scripts.check_forbidden`)

Kết quả: **31/31 thao tác bị chặn đúng** (`r2_30_forbidden.log`). Mọi yêu cầu đều dùng dữ liệu hợp lệ, nên nếu hệ thống trả 2xx thì đó là lỗ hổng thật.

- **EMPLOYEE (15 thao tác), tất cả 403:** tạo sản phẩm, tạo danh mục, sửa giá, nhập kho, xuất kho, kiểm kê, hoàn đơn, xem báo cáo, xuất CSV, xem nhân viên, tạo tài khoản, tạo chi nhánh, bán ở CN02, xem tồn CN02, xem đặt trước CN02.
- **MANAGER (9 thao tác), tất cả 403:** tạo chi nhánh, ngừng chi nhánh, tạo sản phẩm, ngừng bán sản phẩm, xem/khóa nhân viên, báo cáo CN03, nhập kho CN03, bán ở CN03.
- **OWNER của một cửa hàng khác (4 thao tác):** xem và hoàn đơn của DKat trả 404; xem và nhập kho chi nhánh DKat trả 403.
- **Chưa đăng nhập, hoặc gọi API quản trị không có `X-Admin-Token`:** 401.
- **Ẩn menu theo vai trò trên giao diện:** đã kiểm tra ở TC-PA-01..03.

## 4. Trọn luồng đặt trước với SMS/email thật (`python -m scripts.demo_dry_run`)

Kết quả: 10/10 bước (`r2_62_real_flow.log`). Server dùng cấu hình thật trong `.env`, đã bật cả job hết hạn và job gửi lại. Thứ tự các bước: website đặt trước → nhập kho → FIFO (chị Lan được giữ hàng trước) → nhập thêm → thông báo → thu tiền và giao → dashboard.

- **Email thật:** gửi thành công (`SENT`), đơn chuyển NOTIFIED.
- **SMS thật:** eSMS từ chối với mã `TEMPLATE_MISMATCH`. Tài khoản dùng thử chỉ gửi được mẫu tin đã đăng ký với nhà mạng. Đây là giới hạn của nhà cung cấp, không phải lỗi code: hệ thống chuyển sang email đúng thiết kế. Muốn SMS đến máy khách thì cần đăng ký mẫu tin (brandname) với eSMS.

## 5. Hồi quy

| Bộ test | Kết quả | Log |
|---|---|---|
| Unit test, bản clone sạch | 33/35 (2 lỗi của BUG-011) | `r2_70_unit.log` |
| Integration gốc pbi99, pbi110 | Vẫn đỏ (BUG-010) | `r2_71`, `r2_72` |
| Integration đã chỉnh: pbi110, 111, 121, 99, 122 | 16/16, 13/13, 23/23, 16/16, 16/16 | `r2_73` … `r2_78` |
| Integration đã chỉnh: pbi129 (FIFO + hết hạn) | 35/36. Test lifespan nay Đạt; 1 test cần DB cũ nên bị chặn do môi trường | `r2_76` (và `r2_10`) |
| Thông báo, website công khai | 4/4, 5/5 | `r2_79`, `r2_80` |

## Chạy lại

Trong `backend/`, với `DB_NAME=dkat_demo`:

```powershell
python -m scripts.demo_reset; python -m scripts.check_reconciliation; python -m scripts.check_forbidden
python -m scripts.demo_reset; python -m scripts.check_preorder_notify; python -m scripts.check_reconciliation
# Có server (uvicorn) đang chạy:
python -m scripts.demo_reset; python -m scripts.check_pos_auth; python -m scripts.check_reconciliation
python -m scripts.demo_reset; python -m scripts.demo_dry_run; python -m scripts.check_reconciliation
```

# Theo dõi lỗi, kiểm thử và velocity

Ba file Excel dùng chung cho cả nhóm. Ai có quyền push vào repo đều sửa được. **Bản dùng chung nằm trên nhánh `develop`**: sửa và push ở đây, không sửa ở nhánh riêng.

## Các lần chạy kiểm thử

| Ngày | Phạm vi | Kết quả | Chi tiết |
|---|---|---|---|
| 25/11/2026 | Ghép nối trên develop: Auth/POS, Đặt trước/Thông báo | 59 test case: 48 Pass, 10 Fail. 9 bug mới (BUG-005 đến BUG-013), 4 bug mức Cao | [test-runs/2026-11-25-develop](test-runs/2026-11-25-develop/README.md) |
| 25/11/2026 | Diễn tập kịch bản demo (API + giao diện thật) sau khi sửa BUG-005, BUG-008 | 70 test case: 59 Pass. Thêm BUG-014 đến BUG-017 (đã sửa 3), đính chính BUG-007 xuống mức Thấp | [docs/demo/kich-ban-demo.md](../demo/kich-ban-demo.md) |
| 25/11/2026 | Vòng 2: kiểm tra lại bug, đối chiếu số liệu (NFR-04, NFR-11), chức năng bị cấm theo vai trò, luồng đặt trước với SMS/email thật | Không còn bug mức Cao đang mở (12/19 đã đóng); đối chiếu khớp 24/24 ở 4 trạng thái dữ liệu; 31/31 thao tác bị cấm bị chặn đúng; POS & Auth 12/12, Đặt trước & Thông báo 12/12 | [test-runs/2026-11-25-round2](test-runs/2026-11-25-round2/README.md) |

| File | Dùng để | Sheet |
|---|---|---|
| [DKat_Bug_Log.xlsx](DKat_Bug_Log.xlsx) | Ghi và theo dõi bug | `Bug log` (nhập liệu), `Thống kê` (tự tính), `Hướng dẫn` |
| [DKat_Test_Cases.xlsx](DKat_Test_Cases.xlsx) | Viết và ghi kết quả test case | `Test case` (nhập liệu), `Thống kê` (tự tính), `Hướng dẫn` |
| [DKat_Sprint_Tracking.xlsx](DKat_Sprint_Tracking.xlsx) | Bảng theo dõi velocity theo sprint | `Velocity`, `Sprint 1 - task` |

## Bộ test POS & Auth (vòng kiểm thử Ngày 16)

12 test case tích hợp: đăng nhập 3 vai trò, đăng nhập sai, tạo đơn, thanh toán trừ kho, sai số tiền, không đủ tồn, hủy đơn PENDING, hoàn đơn đã thanh toán, phân quyền theo chi nhánh. Mỗi test case ghi dữ liệu cụ thể lấy từ seed `python -m scripts.demo_reset`.

- Sheet **POS & Auth** trong [DKat_Test_Cases.xlsx](DKat_Test_Cases.xlsx): điền Kết quả thực tế, Pass/Fail, Người test, Ngày test khi chạy.
- Bản đọc trên GitHub: [test-cases/pos-auth.md](test-cases/pos-auth.md). Mỗi test case có một GitHub Issue (nhãn `test-case`, `pos-auth`), tạo bằng `test-cases/create_issues.ps1` (hoặc `.sh`).
- Chạy tự động cùng dữ liệu: `python -m scripts.check_pos_auth` (sau `demo_reset`, server đang chạy), in PASS/FAIL 12 test case.
- Sửa test case: sửa [test-cases/pos_auth_cases.py](test-cases/pos_auth_cases.py) rồi chạy `python docs/qa/test-cases/build_test_cases.py` để sinh lại sheet, file md và nội dung issue.

## Bộ test Đặt trước & Thông báo (vòng kiểm thử Ngày 16)

12 test case tích hợp cho luồng phức tạp nhất: đặt trước thiếu tên / SĐT / địa chỉ bị từ chối, đặt trước thành công không trừ kho, nhập kho phân bổ FIFO đúng thứ tự (kể cả phân bổ một phần), đơn đủ hàng -> READY -> SMS, SMS lỗi -> email, thử lại tự động và thủ công, xác nhận nhận hàng mới trừ kho, hủy và hết hạn giải phóng hàng. Kết quả mong đợi ghi bằng số đo được: Tồn thực / Đã giữ / Khả dụng, số lượng đã phân bổ cho từng đơn, trạng thái đơn và từng lần gửi.

- Sheet **Đặt trước & Thông báo** trong [DKat_Test_Cases.xlsx](DKat_Test_Cases.xlsx); bản đọc trên GitHub: [test-cases/preorder-notify.md](test-cases/preorder-notify.md); issue nhãn `preorder-notify`.
- Server chạy theo 2 cấu hình (ghi trong phần Chuẩn bị): A = SMS sandbox, tắt email; B = sai khóa eSMS, email thật. Không có SMS thật nào gửi tới số trong test case.
- Chạy tự động: `python -m scripts.demo_reset` rồi `python -m scripts.check_preorder_notify` (không cần bật server, gửi 2 email thật tới EMAIL_TEST_TO và hộp thư nhóm).
- Dữ liệu nguồn: [test-cases/preorder_notify_cases.py](test-cases/preorder_notify_cases.py).

## Bug log

Cột bắt buộc (tiêu đề xanh lá): **Mã bug, Mô tả, Bước tái hiện, Mức độ, Người phụ trách, Trạng thái**. Cột phụ: Module, Người phát hiện, Ngày phát hiện, Ghi chú / nhánh sửa, Hạn sửa (Cao: 24 giờ).

- Mã bug: `BUG-001`, `BUG-002`, ... tăng dần.
- Mức độ (chọn từ danh sách):
  - **Cao**: chặn nghiệp vụ, sai tiền hoặc dữ liệu, lộ dữ liệu, lỗi 500, lỗ hổng phân quyền.
  - **Trung bình**: sai nhưng có cách làm tạm.
  - **Thấp**: lỗi hiển thị, chính tả.
- Trạng thái: `Mới` → `Đang xử lý` → `Chờ kiểm tra` → `Đã đóng`. Hai trạng thái khác: `Mở lại` (test lại vẫn lỗi) và `Không sửa` (ghi lý do vào Ghi chú).
- Đã có sẵn 4 bug thật, đã sửa trên các nhánh `tuan/*` (BUG-001 đến BUG-004), để làm ví dụ cách ghi.

## Test case

Cột bắt buộc: **ID, Chức năng, Điều kiện, Các bước, Kết quả mong đợi, Kết quả thực tế, Pass/Fail, Người test**. Cột phụ: Ngày test, Ghi chú / Bug liên quan.

- ID: `TC-<MODULE>-<số>`, ví dụ `TC-AUTH-001`, `TC-POS-003`.
- Cột Pass/Fail chọn một trong bốn giá trị: `Pass`, `Fail`, `Chưa test`, `Bị chặn`. Khi `Fail`, tạo bug trong Bug log và ghi mã bug vào cột Ghi chú.
- Đã có sẵn 17 test case backend, đều **Pass** khi chạy ngày 25/11/2026 bằng `check_rbac`, `check_dashboard`, `check_public_catalog`, `check_templates`. Thêm 1 dòng mẫu `TC-PRE-001` (Chưa test) cho module đặt trước.

## Velocity

Velocity = điểm hoàn thành / điểm kế hoạch. Điểm kế hoạch lấy từ `PBI-tong-hop.xlsx` và không tính điểm Bonus.

| Sprint | Kế hoạch | Hoàn thành | Velocity |
|---|---|---|---|
| Sprint 1 (ngày 1-6) | 119 | 119 | **100%** |
| Sprint 2 (ngày 7-12) | 120 | | |
| Sprint 3 (ngày 13-18) | 114 | | |

- Sprint 1: cả 51 task đã được xác nhận hoàn thành. Sheet `Sprint 1 - task` liệt kê từng task kèm trạng thái. Khi đổi trạng thái một task, velocity tự tính lại, cả theo thành viên lẫn cả nhóm.
- Sprint 2 và 3: khi họp tổng kết sprint, nhập số điểm hoàn thành vào ô vàng.

## Quy ước sửa file

Excel là file nhị phân, git không gộp được khi hai người cùng sửa một file. Vì vậy:

1. Chạy `git pull` trước khi mở file.
2. Sửa xong thì đóng Excel, rồi `git add`, `git commit` và `git push` **ngay**.
3. Nếu push bị từ chối: chạy `git pull`, chọn bản trên remote (`git checkout --theirs <file>`), mở lại file đó và nhập lại các dòng của mình.
4. Chỉ thêm dòng mới hoặc sửa dòng của mình. Không xóa dòng của người khác.

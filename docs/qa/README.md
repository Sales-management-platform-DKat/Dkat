# Theo dõi lỗi, kiểm thử và velocity

Ba file Excel dùng chung cho cả nhóm. Ai có quyền push vào repo đều sửa được.

| File | Dùng để | Sheet |
|---|---|---|
| [DKat_Bug_Log.xlsx](DKat_Bug_Log.xlsx) | Ghi và theo dõi bug | `Bug log` (nhập liệu), `Thống kê` (tự tính), `Hướng dẫn` |
| [DKat_Test_Cases.xlsx](DKat_Test_Cases.xlsx) | Viết và ghi kết quả test case | `Test case` (nhập liệu), `Thống kê` (tự tính), `Hướng dẫn` |
| [DKat_Sprint_Tracking.xlsx](DKat_Sprint_Tracking.xlsx) | Bảng theo dõi velocity theo sprint | `Velocity`, `Sprint 1 - task` |

## Bug log

Cột bắt buộc (tiêu đề xanh lá): **Mã bug, Mô tả, Bước tái hiện, Mức độ, Người phụ trách, Trạng thái**. Cột phụ: Module, Người phát hiện, Ngày phát hiện, Ghi chú / nhánh sửa.

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

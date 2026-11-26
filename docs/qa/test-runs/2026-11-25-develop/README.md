# Kiểm thử ghép nối trên develop, 25/11/2026

Mục tiêu: tìm lỗi ghép nối khi còn 2 ngày để sửa. Phạm vi: **Auth/POS** và **Đặt trước/Thông báo**.

- Kết quả từng test case: [DKat_Test_Cases.xlsx](../../DKat_Test_Cases.xlsx), sheet `Test case`, các dòng `TC-DEV-*`.
- Bug: [DKat_Bug_Log.xlsx](../../DKat_Bug_Log.xlsx), từ `BUG-005` đến `BUG-013`.
- Bằng chứng: thư mục [logs/](logs/) ghi mọi request và response, log server, log của từng bộ test. Tên tệp có trong cột Ghi chú của từng test case.

## 1. Môi trường

| Mục | Giá trị |
|---|---|
| Code | Nhánh `develop`, tạo từ `master` commit `333a38b` (code đã merge: các nhánh `tuiladien/*`, `ngtrongkhanq`, phần port của Khang) |
| Chưa có trong develop | Các nhánh `tuan/*` chưa được merge. Chỉ phần khách hàng và báo cáo đã được port, **chưa có thông báo SMS/email** (xem BUG-005) |
| Database | MySQL 8.0.45 local. Database **mới tạo** `dkat_develop` từ `database/01_schema.sql` (22 bảng) |
| Dữ liệu seed | Không có seed nào chạy được (BUG-009). Seed hoàn toàn qua API bằng [scripts/seed_develop.py](scripts/seed_develop.py): 1 cửa hàng, CN01-CN03, `owner01`, `manager01` (CN01, CN02), `staff01` (CN01), `locked01` (đã khóa), 1 sản phẩm 3 biến thể. Size S và M mỗi loại tồn 10 tại CN01, Size L hết hàng |
| Mật khẩu thử | `Dkat@12345678`, chỉ dùng cho DB thử nghiệm một lần (develop bắt buộc mật khẩu từ 12 ký tự) |
| Đăng nhập | OWNER dùng `owner01`. Tài khoản nhân viên dùng `manager01:manager` và `staff01:staff` |
| Kết nối DB | Phải chạy qua [scripts/localdb.py](scripts/localdb.py) để tắt xác minh SSL, nếu không develop không kết nối được MySQL local (BUG-008) |

## 2. Kết quả

| Bộ kiểm thử | Kết quả | Log |
|---|---|---|
| E2E Auth và phân quyền (server thật, 9 case) | **9/9 Pass** | `22_e2e_requests.log` |
| E2E POS (9 case) | **8/9**. Fail POS-09: `createdAt` lệch 7 giờ (BUG-012) | `22_e2e_requests.log` |
| E2E Đặt trước (10 case) | **8/10**. Fail PRE-03: form POS gửi sai body (BUG-007). Fail PRE-10: job hết hạn không chạy (BUG-006) | `22_e2e_requests.log` |
| E2E Thông báo (3 case) | **0/3**. Không có bản ghi thông báo, API 404 (BUG-005) | `22_e2e_requests.log`, `20_server_develop.log` |
| Unit test backend (SQLite) | 29/31 (BUG-011) | `01_unit_tests.log` |
| 6 bộ integration test MySQL, bản gốc | 0/6 bộ chạy được (BUG-008, BUG-010) | `02..07_it_*.log` |
| Cùng 6 bộ, chỉ sửa đường dẫn `/api/v1` và payload tạo tài khoản | pbi110 16/16, pbi121 23/23, pbi99 16/16, pbi122 16/16, pbi111 13/13. pbi129 34/36: 1 Fail (BUG-006), 1 bị chặn do cần DB cũ | `12..17_qa_*.log` |
| Frontend `npm test` và `npm run build` | 31/31, build thành công | `31_*.log`, `32_*.log` |

**Tổng cộng trong file Test case: 59 test case, 48 Pass, 10 Fail, 1 Chưa test (TC-PRE-001 cũ, nay đã thay bằng TC-DEV-PRE-01).**

Phần chạy tốt: đăng nhập, đăng xuất, khóa tài khoản, phân quyền theo chi nhánh, toàn bộ luồng POS (tạo đơn, chặn vượt tồn, thanh toán sai hoặc đúng số tiền, hủy, hoàn tiền, hoàn kho, gắn khách), luồng đặt trước của khách (tạo đơn, chặn khi còn hàng, giới hạn 5 lần / 10 phút / IP, phân bổ FIFO khi nhập hàng, thanh toán, giao hàng, trừ kho, hủy).

## 3. Phân loại bug (đề xuất cho buổi họp 15 phút)

Quy tắc: mức **Cao sửa trong 24 giờ** (trước 26/11/2026). Trung bình và Thấp sửa trước 27/11/2026.

| Bug | Mức độ | Người phụ trách | Hạn | Nội dung | Xác nhận trong họp |
|---|---|---|---|---|---|
| BUG-005 | Cao | Tuấn | 26/11 | Thông báo đặt trước không gửi: module notifications rỗng trên develop. Cần port bản sync | ☐ |
| BUG-006 | Cao | Khang (Điền review) | 26/11 | Job tự hủy đơn quá hạn bị mất ở merge `9cc2512` | ☐ |
| BUG-007 | Cao | Quốc Anh | 26/11 | Form đặt trước tại quầy (`LivePos.jsx`) luôn 422 | ☐ |
| BUG-008 | Cao | Khang | 26/11 | Bắt buộc SSL nên không chạy được với MySQL local | ☐ |
| BUG-009 | Trung bình | Tuấn | 27/11 | Không có seed chạy được trên develop | ☐ |
| BUG-010 | Trung bình | Điền | 27/11 | 6 bộ integration test lệch hợp đồng API | ☐ |
| BUG-011 | Trung bình | Khang | 27/11 | 2 unit test báo cáo lỗi `no such table` | ☐ |
| BUG-012 | Thấp | Điền | 27/11 | `createdAt` lệch 7 giờ khi MySQL chạy giờ +07 | ☐ |
| BUG-013 | Thấp | Khang | 27/11 | README backend lệch với code | ☐ |

Thứ tự đề xuất: BUG-008 trước, vì khi sửa xong mọi người chạy test local được. Sau đó đến BUG-005, 006, 007. Sửa xong bug nào thì người phụ trách đổi trạng thái sang `Chờ kiểm tra`, Tuấn chạy lại test case liên quan rồi đóng bug.

## 4. Chạy lại

Cần MySQL 8 local và Python 3.12 trở lên. Các script nằm trong [scripts/](scripts/).

```bash
# 1. Tạo database sạch (chỉ chấp nhận tên dkat_develop / dkat_pbi*_test, sẽ DROP rồi tạo lại)
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=root DB_PASSWORD=...
python scripts/setup_dbs.py database/01_schema.sql dkat_develop
# 2. Bật server develop (cổng 8010), DKAT_ADMIN_TOKEN >= 32 ký tự, lưu token vào qa/.admin_token
cd backend && DB_NAME=dkat_develop DKAT_ADMIN_TOKEN=... DKAT_AUTH_SECRET_KEY=... \
  python <qa>/localdb.py -m uvicorn app.main:app --port 8010
# 3. Seed qua API rồi chạy E2E (cùng thư mục với e2e_lib.py)
python seed_develop.py && python e2e_develop.py
```

Integration test theo hợp đồng mới: chép `integration_tests/` sang `integration_tests_qa/`, dùng [scripts/integration_tests_qa__init__.py](scripts/integration_tests_qa__init__.py) làm `__init__.py` (tự thêm tiền tố `/api/v1`), đổi `"plan": "pro"` thành `"plan": "basic"` và thêm `owner_email`. Sau đó chạy `python localdb.py -m unittest -v integration_tests_qa.<bộ>` với `DB_NAME` và cờ `DKAT_*_TEST_DB=1` tương ứng.

# Hợp đồng gọi hàm giữa các module

Tài liệu này chốt chữ ký các hàm mà module khác gọi trực tiếp trong code, không qua HTTP. Mỗi lần đổi chữ ký hoặc ý nghĩa của các hàm này phải cập nhật tài liệu và báo người đang gọi.

## NotificationService.notifyPreorder (FR-09.1 đến FR-09.4)

- **Bên cung cấp:** Tuấn, `backend/app/modules/notifications/service.py`
- **Bên gọi:** Điền, `preorders/services/notifications.py` (`notify_ready_preorders`) và worker hết hạn đơn
- **Trạng thái:** đã chốt ngày 24/11/2026 (trước Ngày 15)

### Chữ ký

```python
from app.modules.notifications.service import NotificationService

outcome: dict = NotificationService.notifyPreorder(preorder_id: int, event_type: str)
```

| Tham số | Giá trị |
|---|---|
| `preorder_id` | `preorders.preorder_id` |
| `event_type` | `"PREORDER_CREATED"`, `"PREORDER_READY"`, `"PREORDER_CANCELLED"`, `"PREORDER_EXPIRED"` (`NotificationService.EVENT_TYPES`) |

Kết quả trả về là một dict, **không bao giờ ném lỗi**:

```json
{
  "preorderId": 62,
  "eventType": "PREORDER_READY",
  "status": "SENT",
  "finalChannel": "EMAIL",
  "notificationIds": [35, 36],
  "error": "SMS TEMPLATE_MISMATCH: ..."
}
```

| `status` | Ý nghĩa |
|---|---|
| `SENT` | Có một kênh gửi thành công. `finalChannel` là kênh đó. |
| `FAILED` | Mọi kênh đều lỗi. Các dòng `notifications` ở trạng thái `FAILED`, lý do nằm trong `error`. |
| `SKIPPED` | Không gửi gì và không ghi dòng nào: `UNKNOWN_EVENT`, `PREORDER_NOT_FOUND`, `NO_CONTACT`. |
| `SCHEDULED` | Hàm được gọi từ chính event loop nên không thể chờ. Việc gửi chạy nền; kết quả xem trong bảng `notifications`. |

### Cách gọi

| Bên gọi | Dùng | Ghi chú |
|---|---|---|
| Route `def` (đồng bộ) trong FastAPI, chạy sau khi đã commit | `NotificationService.notifyPreorder(...)` | Chạy xong mới trả về. Chỉ chặn worker thread, không chặn server. Đây chính là cách code hiện tại của Điền đang gọi. |
| Worker hoặc script chạy ở tiến trình riêng | `NotificationService.notifyPreorder(...)` | Hàm tự tạo event loop riêng. |
| Code `async` muốn lấy kết quả | `await NotificationService.notifyPreorderAsync(...)` | Trả về `NotificationOutcome`; dùng `.to_dict()` để có dict như trên. |
| Không cần chờ kết quả | `NotificationService.schedulePreorder(...)` hoặc `background_tasks.add_task(NotificationService.notifyPreorderAsync, ...)` | Trả về ngay. Dùng `BackgroundTasks` thì việc gửi diễn ra sau khi response đã gửi cho client. |

**Phải gọi SAU khi transaction của đơn đã commit.** Service đọc đơn và ghi `notifications` bằng phiên DB riêng, nên nếu gọi trước khi commit sẽ đọc phải dữ liệu cũ.

### Quy tắc kênh

1. **Đơn có SĐT thì gửi SMS trước.**
   - eSMS từ chối ngay (ví dụ mã 146: sai mẫu tin) thì tính là SMS lỗi.
   - eSMS đã nhận nhưng nhà mạng từ chối thì cũng tính là SMS lỗi (lỗi `CARRIER_REJECTED`). Để phát hiện trường hợp này, service tra trạng thái gửi tối đa `NOTIFY_SMS_CONFIRM_SECONDS` (mặc định 30 giây). Hết thời gian chờ mà chưa có kết quả thì coi là đã gửi.
2. **SMS lỗi (hoặc đơn không có SĐT) mà đơn có email thì gửi email.**
3. **`finalChannel` là kênh được thử sau cùng.**

### Bảng `notifications`: mỗi lần thử gửi một dòng

| Cột | Giá trị |
|---|---|
| `channel` | `SMS` hoặc `EMAIL` |
| `recipient` | SĐT dạng `0xxxxxxxxx` hoặc địa chỉ email |
| `message` | Nội dung SMS **đúng như đã gửi** (đã bỏ dấu); với email là tiêu đề + nội dung |
| `status` | `PENDING` (ghi và commit trước khi gửi), sau đó chuyển sang `SENT` hoặc `FAILED` |
| `provider_message_id` | SMS: SMSID của eSMS. Email: `Message-ID` của thư. |
| `error_message` | `MÃ: mô tả`, ví dụ `TEMPLATE_MISMATCH: ...`, `CARRIER_REJECTED: ...`, `SMTP_AUTH_FAILED: ...` |
| `sent_at` | Giờ **UTC** lúc nhà cung cấp nhận tin. `NULL` khi gửi lỗi. |

`RequestId` gửi sang eSMS là `notification-<notification_id>`, nên một dòng không bao giờ bị eSMS gửi hai lần.

### Thời gian và cam kết

- **Không ném lỗi và không động vào transaction của bên gọi.** Lỗi gửi chỉ ghi log (log chỉ có id và mã lỗi, không có SĐT, email hay nội dung tin) và để dòng ở trạng thái `FAILED`.
- **Thời gian chạy tối đa** khi gọi đồng bộ: khoảng 10 giây gửi SMS + 30 giây xác nhận SMS + 10 giây gửi email. Nếu cần trả response nhanh, dùng `BackgroundTasks` hoặc giảm `NOTIFY_SMS_CONFIRM_SECONDS` (đặt 0 thì không chờ xác nhận, nhưng khi đó sẽ không chuyển sang email nếu nhà mạng từ chối sau).
- **Mỗi lần gọi đều gửi lại.** Service không chống gửi trùng theo sự kiện, nên bên gọi chỉ gọi một lần cho mỗi sự kiện.
- **Service không đổi trạng thái đơn.** Việc chuyển `READY` sang `NOTIFIED` vẫn do bên preorders làm. Câu SQL hiện tại của Điền (kiểm tra có dòng `notifications` `SENT`) vẫn dùng được, hoặc dùng luôn `outcome["status"] == "SENT"`.

### Cấu hình (`.env`)

| Biến | Dùng cho |
|---|---|
| `SMTP_*` | Email (`core/mailer.py`) |
| `ESMS_*`, `SMS_*` | SMS (`core/sms.py`) |
| `NOTIFY_SMS_CONFIRM_SECONDS` (30), `NOTIFY_SMS_POLL_SECONDS` (5) | Thời gian chờ xác nhận SMS |

**Tài khoản eSMS dùng thử** chỉ gửi được mẫu tin thử của eSMS. Mọi nội dung thông báo thật hiện bị trả `TEMPLATE_MISMATCH` và tự chuyển sang email. Cần đăng ký brandname và mẫu tin với eSMS thì SMS mới tới được khách.

### Kiểm tra

```powershell
cd backend
python -m scripts.notify_preorder --sample                    # đơn mẫu PD-MAU-THONGBAO, gửi tới SMS_TEST_TO / EMAIL_TEST_TO
python -m scripts.notify_preorder --preorder-id 42 --event PREORDER_CANCELLED
```

Kết quả chạy thật ngày 24/11/2026 với đơn mẫu (`PREORDER_READY`):

| # | Kênh | Trạng thái | Ghi chú |
|---|---|---|---|
| 35 | SMS | FAILED | eSMS 146: tài khoản dùng thử từ chối nội dung không theo mẫu |
| 36 | EMAIL | SENT | Đã gửi thật, có `Message-ID` |

Kết quả cuối: `status = SENT`, `finalChannel = EMAIL`.

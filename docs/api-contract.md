# Hợp đồng gọi hàm giữa các module

Tài liệu này chốt chữ ký các hàm mà module khác gọi trực tiếp trong code, không qua HTTP. Mỗi lần đổi chữ ký hoặc ý nghĩa của các hàm này phải cập nhật tài liệu và báo người đang gọi.

Danh sách đầy đủ các **HTTP endpoint**, sinh tự động từ code: [api-endpoints.md](api-endpoints.md) và [openapi.json](openapi.json). Lệnh `python -m scripts.check_api_docs` kiểm tra mọi endpoint, hàm và cấu hình được nhắc trong tài liệu này có thật trong code.

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

## Thử lại thông báo lỗi (FR-09.5, NFR-10)

- **Bên cung cấp:** Tuấn, `backend/app/modules/notifications/retry.py` và `router.py`
- **Cần chạy migration:** `database/09_notification_retry.sql` (thêm các cột `retry_count`, `event_type`, `last_attempt_at` và index `ix_notifications_retry`)

### Job tự động

Job khởi động cùng app và chạy mỗi `NOTIFY_RETRY_INTERVAL_SECONDS` (mặc định 300 giây = 5 phút). Muốn chạy ngay một lượt: `python -m scripts.retry_notifications`.

**Job chọn các dòng thỏa cả 3 điều kiện:**
- `status = 'FAILED'` và `retry_count < NOTIFY_MAX_RETRIES` (mặc định 3);
- **lỗi không thuộc loại cố định:** `INVALID_INPUT`, `INVALID_PHONE`, `TEMPLATE_MISMATCH`, `BRANDNAME_INVALID`, `CARRIER_NOT_REGISTERED`, `CARRIER_REJECTED`, `BLOCKED_KEYWORD`, `PHONE_BLOCKED`, `UNSUPPORTED_TYPE`, `RECIPIENT_REFUSED`. Gửi lại cùng nội dung cho cùng người nhận thì các lỗi này vẫn lặp lại;
- **sau dòng đó, đơn chưa có thông báo nào `SENT`.** Ví dụ SMS lỗi nhưng email chuyển sang đã tới khách, thì không gửi lại SMS, để khách không nhận hai lần.

**Mỗi lần gửi lại:**
- Gửi lại **chính dòng đó**: cùng kênh, cùng người nhận, cùng nội dung đã lưu. Riêng SMS dùng `RequestId` mới (`notification-<id>-r<lần>`).
- `retry_count` tăng thêm 1, `last_attempt_at` được cập nhật. Kết quả ghi đè `status`, `provider_message_id`, `error_message`, `sent_at`.
- Hết 3 lần vẫn lỗi thì dòng giữ `FAILED`, và `error_message = "RETRY_EXHAUSTED: đã gửi lại 3 lần vẫn lỗi, dừng tự động. Lỗi cuối: ..."`.

**Không gửi trùng:** trước khi gửi, dòng được "giành" bằng một lệnh UPDATE nguyên tử `FAILED → PENDING`. Job và nhân viên bấm cùng lúc, hoặc server chạy nhiều worker, thì vẫn chỉ một bên gửi.

### API

| Endpoint | Quyền | Kết quả |
|---|---|---|
| `GET /api/v1/preorders/{id}/notifications` | Mọi nhân viên, trong chi nhánh của mình (khác chi nhánh → 403) | `{preorderId, preorderCode, maxAutoRetries, items[{id, preorderId, eventType, channel, recipient (đã che), message, status, retryCount, canResend, providerMessageId, errorMessage, sentAt, lastAttemptAt, createdAt}]}`, dòng cũ nhất trước |
| `POST /api/v1/notifications/{id}/resend` | Mọi nhân viên, trong chi nhánh của mình | Gửi lại ngay, kể cả khi đã hết lượt tự động. 200 `{result: "SENT" \| "FAILED", notification}`. Thông báo đang `SENT` hoặc đang được gửi (`PENDING`) → 409 `NOTIFICATION_NOT_FAILED`. Không tồn tại → 404. |

### Kiểm thử thật ngày 24/11/2026 (Gmail)

| Kịch bản | Diễn biến |
|---|---|
| Sai khóa | Dòng #103 `FAILED` (`SMTP_AUTH_FAILED` 535) → sửa mật khẩu → `POST /notifications/103/resend` → 200, `SENT`, `retry_count = 1` |
| Mất mạng | Dòng #104 `FAILED` (`CONNECTION_FAILED`) → khôi phục → job chạy một lượt → `SENT`, `retry_count = 1` |

## Nội dung thông báo theo trạng thái thanh toán (FR-09.6)

Khi gọi `notifyPreorder(id, "PREORDER_READY")`, service tự chọn mẫu theo `preorders.payment_status`:

| `payment_status` | Mẫu | Nội dung |
|---|---|---|
| `PAID` | Mẫu 2 `PREORDER_READY_PAID` | Hàng đã sẵn sàng; liên hệ SĐT cửa hàng để chọn nhận tại cửa hàng hoặc giao tận nơi; giữ đến `<hạn>` |
| `UNPAID`, `REFUNDED` | Mẫu 1 `PREORDER_READY_UNPAID` | Hàng đã có tại `<chi nhánh>`; mời đến mua trước `<hạn giữ hàng>` |

**Hàm:** `render_template(template_type, data) -> RenderedTemplate(sms, email_subject, email_body, email_html)` trong `modules/notifications/templates.py`. Đây là hàm thuần: không đọc DB, không gửi. Các khóa của `data`:

- `customer_name`, `preorder_code`, `branch_name`, `branch_address`, `contact_phone`
- `hold_until`: giờ Việt Nam
- `items`: danh sách `[{name, sku, quantity, unit_price, line_total}]`
- `total_amount`

**Nguồn dữ liệu:**
- **Hạn giữ hàng** = `preorders.expires_at` (UTC, cần migration `database/07_preorder_fifo_expiry.sql`), đổi sang giờ Việt Nam. Đơn chưa có `expires_at` thì dùng `ready_at + PREORDER_READY_DAYS` (mặc định 7, cùng quy tắc với module preorders).
- **SĐT liên hệ** = `branches.phone`. Chi nhánh không có SĐT thì dùng `STORE_CONTACT_PHONE`.
- **Sản phẩm** lấy từ snapshot `preorder_items` (tên, SKU, số lượng, thành tiền).

**SMS:** luôn vừa **1 tin** (160 ký tự sau khi bỏ dấu). Nếu dài, service rút gọn theo thứ tự: viết "Chi nhánh" thành "CN", cắt ngắn tên sản phẩm, cắt ngắn tên chi nhánh, cuối cùng mới bỏ lời chào có tên. Mã đơn và hạn giữ hàng luôn được giữ lại.

**Email:** có bản text (lưu vào `notifications.message`) và bản HTML (bảng sản phẩm, số lượng, thành tiền, tổng tiền). Mọi dữ liệu do người dùng nhập đều được escape. Khi gửi lại một thông báo, chỉ gửi bản text.

Các sự kiện `PREORDER_CREATED`, `PREORDER_CANCELLED`, `PREORDER_EXPIRED` vẫn dùng nội dung cũ.

**Kiểm thử:**
- `python -m scripts.check_templates`: 2 mẫu × 2 kênh, in ra 4 bản nội dung.
- Gửi thật: `python -m scripts.notify_preorder --sample --payment UNPAID` (hoặc `--payment PAID`).

"""Reusable SMS sender over eSMS.vn (FR-09.1: pre-order notifications).

    result = await send_sms(to="0912 345 678", content="Don PD-001 da co hang ...")
    result.success / result.provider_message_id (eSMS SMSID) / result.error   # same shape as send_email

API (https://developers.esms.vn, checked 2026-11):
- POST {ESMS_BASE_URL}/SendMultipleMessage_V4_post_json/  body: ApiKey, SecretKey, Phone, Content,
  Brandname, SmsType ("2" = brandname CSKH), IsUnicode, Sandbox, RequestId, CallbackUrl.
- Response {"CodeResult": "100", "SMSID": "..."}: 100 only means eSMS ACCEPTED the request; the final
  delivery status comes later (CallbackUrl or GetSendStatus).
- Trial accounts may only send the registered test template with brandname "Baotrixemay":
  "<CODE> la ma xac minh dang ky Baotrixemay cua ban" (CODE: up to 8 letters/digits); any other content
  fails with 146. The same phone + same content is accepted once per 5 minutes.

Rules (same contract as core/mailer.send_email):
- Configured only through .env (ESMS_*, SMS_*). NEVER raises: every failure becomes
  SmsResult(success=False, error="CODE: detail"), so a failed SMS never breaks the business flow.
- Phone numbers are normalized to the domestic form 0xxxxxxxxx (mobile prefixes 03/05/07/08/09 only).
- SMS_UNICODE=false: Vietnamese accents are removed (đ -> d) so the text fits 160 chars per part.
  Content longer than SMS_MAX_PARTS parts is refused.
- One deadline of SMS_TIMEOUT_SECONDS (10 s) for the whole HTTP call.
- Logs never contain the API keys or the content, and mask the phone number.
"""
import asyncio
import re
import unicodedata
import uuid

import httpx

from app.core.config import settings
from app.core.mailer import EmailResult
from app.utils.logger import get_logger

logger = get_logger("app.sms")

# Same result type as send_email: {success, providerMessageId, error}
SmsResult = EmailResult

MOBILE_PATTERN = re.compile(r"0[35789]\d{8}")
# GSM 03.38 basic charset (what a non-unicode SMS can carry) and the extension chars that cost 2
GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENSION = set("^{}\\[~]|€")

# eSMS CodeResult -> our error code (docs: https://developers.esms.vn/esms-api/bang-ma-loi)
ESMS_ERRORS = {
    "99": ("PHONE_BLOCKED", "số điện thoại bị chặn trên hệ thống eSMS"),
    "101": ("AUTH_FAILED", "sai ESMS_API_KEY hoặc ESMS_SECRET_KEY"),
    "102": ("ACCOUNT_ERROR", "tài khoản eSMS chưa có bảng giá"),
    "103": ("QUOTA_EXCEEDED", "số dư / hạn mức tin thử của tài khoản eSMS đã hết"),
    "104": ("BRANDNAME_INVALID", "brandname không tồn tại hoặc chưa kích hoạt"),
    "108": ("INVALID_PHONE", "eSMS báo số điện thoại không đúng định dạng"),
    "118": ("UNSUPPORTED_TYPE", "loại tin (ESMS_SMS_TYPE) không được hỗ trợ"),
    "124": ("DUPLICATE_REQUEST", "RequestId đã được dùng trong 24 giờ qua"),
    "140": ("IP_NOT_WHITELISTED", "IP máy chủ chưa được eSMS cho phép"),
    "143": ("ACCOUNT_ERROR", "tài khoản eSMS chưa kích hoạt hoặc đã bị khóa"),
    "146": ("TEMPLATE_MISMATCH", "nội dung không khớp mẫu tin CSKH đã đăng ký"),
    "177": ("CARRIER_NOT_REGISTERED", "brandname chưa đăng ký với nhà mạng của số này"),
    "201": ("BLOCKED_KEYWORD", "nội dung chứa từ khóa bị chặn"),
}


def normalize_phone(phone: str) -> str:
    """'0912 345 678', '+84912345678', '84912345678', '0912.345.678' -> '0912345678'.
    Raises ValueError unless it is a Vietnamese mobile number (only mobiles receive SMS)."""
    value = re.sub(r"[\s().-]", "", str(phone).strip())
    if value.startswith("+84"):
        value = "0" + value[3:]
    elif value.startswith("84") and len(value) == 11:
        value = "0" + value[2:]
    if not MOBILE_PATTERN.fullmatch(value):
        raise ValueError(value)
    return value


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone))
    return digits[:4] + "***" + digits[-3:] if len(digits) >= 8 else "***"


def remove_accents(text: str) -> str:
    """'Đơn hàng đã về' -> 'Don hang da ve'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def count_parts(text: str, unicode: bool) -> int:
    """Number of SMS parts: GSM 160/153 per part (extension chars count 2), unicode 70/67."""
    if unicode:
        length, single, multi = len(text), 70, 67
    else:
        length, single, multi = sum(2 if c in GSM_EXTENSION else 1 for c in text), 160, 153
    return 1 if length <= single else -(-length // multi)


def prepare_content(content: str, unicode: bool) -> tuple[str | None, str | None]:
    """(text to send, None) or (None, error)."""
    if not isinstance(content, str) or not content.strip():
        return None, "INVALID_INPUT: nội dung tin nhắn bắt buộc"
    text = " ".join(content.split())  # one line, single spaces
    if not unicode:
        text = remove_accents(text)
        bad = sorted({c for c in text if c not in GSM_BASIC and c not in GSM_EXTENSION})
        if bad:
            return None, f"INVALID_INPUT: ký tự không gửi được khi SMS_UNICODE=false: {''.join(bad)[:20]}"
    parts = count_parts(text, unicode)
    if parts > settings.SMS_MAX_PARTS:
        limit = (153 if not unicode else 67) * settings.SMS_MAX_PARTS
        return None, f"INVALID_INPUT: nội dung dài {parts} tin (tối đa {settings.SMS_MAX_PARTS} tin, ~{limit} ký tự)"
    return text, None


def _config_error() -> str | None:
    missing = [k for k in ("ESMS_API_KEY", "ESMS_SECRET_KEY", "ESMS_BRANDNAME") if not getattr(settings, k)]
    return f"NOT_CONFIGURED: thiếu {', '.join(missing)} trong .env" if missing else None


def _provider_error(body: dict) -> str:
    code = str(body.get("CodeResult", body.get("CodeResponse", "")))
    our_code, meaning = ESMS_ERRORS.get(code, ("PROVIDER_ERROR", "eSMS từ chối yêu cầu"))
    detail = str(body.get("ErrorMessage") or body.get("error") or "")[:150]
    return f"{our_code}: {meaning} (eSMS {code or '?'}{': ' + detail if detail else ''})"


async def send_sms(
    to: str,
    content: str,
    *,
    request_id: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SmsResult:
    """Send one SMS through eSMS. Always returns an SmsResult, never raises.

    request_id: pass a stable id (e.g. "notification-42") when retrying the same notification:
    eSMS rejects a RequestId seen in the last 24 h (DUPLICATE_REQUEST) instead of sending twice.
    transport: only for tests (httpx.MockTransport).
    """
    masked = mask_phone(to)
    try:
        try:
            phone = normalize_phone(to)
        except ValueError:
            return _fail(masked, "INVALID_PHONE: số điện thoại phải là số di động Việt Nam (03/05/07/08/09 + 8 số)")
        text, error = prepare_content(content, settings.SMS_UNICODE)
        error = error or _config_error()
        if error:
            return _fail(masked, error)

        payload = {
            "ApiKey": settings.ESMS_API_KEY,
            "SecretKey": settings.ESMS_SECRET_KEY,
            "Phone": phone,
            "Content": text,
            "Brandname": settings.ESMS_BRANDNAME,
            "SmsType": settings.ESMS_SMS_TYPE,
            "IsUnicode": "1" if settings.SMS_UNICODE else "0",
            "Sandbox": "1" if settings.ESMS_SANDBOX else "0",
            "RequestId": (request_id or uuid.uuid4().hex)[:50],
        }
        if settings.ESMS_CALLBACK_URL:
            payload["CallbackUrl"] = settings.ESMS_CALLBACK_URL

        timeout = settings.SMS_TIMEOUT_SECONDS
        url = settings.ESMS_BASE_URL.rstrip("/") + "/SendMultipleMessage_V4_post_json/"
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await asyncio.wait_for(client.post(url, json=payload), timeout=timeout)
        if response.status_code != 200:
            return _fail(masked, f"HTTP_ERROR: eSMS trả HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            return _fail(masked, "INVALID_RESPONSE: eSMS trả dữ liệu không phải JSON")
        if not isinstance(body, dict):
            return _fail(masked, "INVALID_RESPONSE: eSMS trả dữ liệu không đúng dạng")
        if str(body.get("CodeResult")) == "100":
            sms_id = body.get("SMSID")
            logger.info("SMS_ACCEPTED to=%s sms_id=%s sandbox=%s", masked, sms_id, settings.ESMS_SANDBOX)
            return SmsResult(success=True, provider_message_id=str(sms_id) if sms_id else None)
        return _fail(masked, _provider_error(body))
    except Exception as exc:  # noqa: BLE001 - by contract no failure escapes (CancelledError is not caught)
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
            return _fail(masked, f"TIMEOUT: eSMS không phản hồi trong {settings.SMS_TIMEOUT_SECONDS:g} giây")
        if isinstance(exc, httpx.TransportError):
            return _fail(masked, f"CONNECTION_FAILED: không kết nối được eSMS ({exc.__class__.__name__})")
        return _fail(masked, f"UNKNOWN_ERROR: {exc.__class__.__name__}")


def _fail(masked_phone: str, error: str) -> SmsResult:
    # ASCII-only log line: the error code (the Vietnamese detail is in the result)
    logger.warning("SMS_FAILED to=%s error=%s", masked_phone, error.split(":")[0])
    return SmsResult(success=False, error=error)


async def get_send_status(sms_id: str, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Final outcome of an accepted SMS (eSMS GetSendStatus, last 7 days only).

    {'status': 'DELIVERED' | 'FAILED' | 'PENDING' | 'UNKNOWN', 'sendSuccess', 'sendFailed', 'error'}
    eSMS SendStatus: 1 waiting for approval, 2 waiting to send, 5 finished (then SendSuccess /
    SendFailed tell the result). A message sent seconds ago may answer 105 (not found yet) -> PENDING.
    Never raises.
    """
    if error := _config_error():
        return {"status": "UNKNOWN", "sendSuccess": 0, "sendFailed": 0, "error": error}
    try:
        async with httpx.AsyncClient(timeout=settings.SMS_TIMEOUT_SECONDS, transport=transport) as client:
            r = await client.get(
                settings.ESMS_BASE_URL.rstrip("/") + "/GetSendStatus",
                params={"RefId": sms_id, "ApiKey": settings.ESMS_API_KEY, "SecretKey": settings.ESMS_SECRET_KEY},
            )
        body = r.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNKNOWN", "sendSuccess": 0, "sendFailed": 0, "error": f"CONNECTION_FAILED: {exc.__class__.__name__}"}
    code = str(body.get("CodeResponse"))
    if code == "105":
        return {"status": "PENDING", "sendSuccess": 0, "sendFailed": 0, "error": None}
    if code != "100":
        return {"status": "UNKNOWN", "sendSuccess": 0, "sendFailed": 0, "error": _provider_error(body)}
    ok, failed = int(body.get("SendSuccess") or 0), int(body.get("SendFailed") or 0)
    if str(body.get("SendStatus")) != "5":
        status = "PENDING"
    else:
        status = "DELIVERED" if ok > 0 and failed == 0 else "FAILED" if failed > 0 else "UNKNOWN"
    return {"status": status, "sendSuccess": ok, "sendFailed": failed, "error": None}


async def get_balance(transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """{'success', 'balance', 'error'}: eSMS account balance (used by scripts/send_test_sms.py)."""
    if error := _config_error():
        return {"success": False, "balance": None, "error": error}
    try:
        async with httpx.AsyncClient(timeout=settings.SMS_TIMEOUT_SECONDS, transport=transport) as client:
            # The trailing slash is required: without it eSMS answers 307 + an HTML page
            r = await client.post(
                settings.ESMS_BASE_URL.rstrip("/") + "/GetBalance_json/",
                json={"ApiKey": settings.ESMS_API_KEY, "SecretKey": settings.ESMS_SECRET_KEY},
            )
        try:
            body = r.json()
        except ValueError:
            return {"success": False, "balance": None, "error": f"INVALID_RESPONSE: eSMS trả HTTP {r.status_code}, không phải JSON"}
        if str(body.get("CodeResponse")) == "100":
            return {"success": True, "balance": body.get("Balance"), "error": None}
        return {"success": False, "balance": None, "error": _provider_error(body)}
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, httpx.TimeoutException):
            return {"success": False, "balance": None, "error": "TIMEOUT: eSMS không phản hồi"}
        return {"success": False, "balance": None, "error": f"CONNECTION_FAILED: {exc.__class__.__name__}"}

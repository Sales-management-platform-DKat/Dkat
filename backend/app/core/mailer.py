"""Reusable email sender over SMTP (FR-09.2: pre-order notifications).

    result = await send_email(to="khach@example.com", subject="Hàng đã về", body="Xin chào ...")
    if result.success: ... result.provider_message_id ...
    else:               ... result.error ...           # e.g. "SMTP_AUTH_FAILED: ..."

Rules:
- Configured only through .env (SMTP_* in core/config.py); nothing is hard-coded.
- NEVER raises: every problem (missing config, bad password, timeout, refused recipient, network,
  invalid input) becomes EmailResult(success=False, error="CODE: detail"), so a failed email can
  never break the business flow that sends it (e.g. stock import -> notify pre-orders).
- The whole send is limited to SMTP_TIMEOUT_SECONDS (10 s): connect + TLS + login + send.
- provider_message_id: SMTP has no provider id, so it is the Message-ID header generated here
  (unique, and visible in the recipient's mailbox for tracing). Store it in notifications.provider_message_id.
- Logs never contain the password or the body, and mask the recipient address.
"""
import asyncio
import re
import smtplib
import socket
import ssl
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger("app.mailer")

EMAIL_PATTERN = re.compile(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+")
MAX_SUBJECT = 255


@dataclass(frozen=True)
class EmailResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """{success, providerMessageId, error} for JSON / API responses."""
        d = asdict(self)
        return {"success": d["success"], "providerMessageId": d["provider_message_id"], "error": d["error"]}


def mask_email(address: str) -> str:
    """'nguyen.van.a@gmail.com' -> 'n***@gmail.com' (for logs).

    Control characters are removed first: an address like 'a@b.com\\r\\nfake log line' must not be
    able to write extra lines into the log (log injection)."""
    address = re.sub(r"[\x00-\x1f\x7f]", "", str(address))
    local, _, domain = address.partition("@")
    domain = re.sub(r"[^A-Za-z0-9.-]", "?", domain)[:100]
    return f"{local[:1]}***@{domain}" if domain else "***"


def _validate(to: str, subject: str, body: str) -> str | None:
    if not isinstance(to, str) or not EMAIL_PATTERN.fullmatch(to.strip()):
        return "INVALID_INPUT: địa chỉ người nhận không hợp lệ"
    if not isinstance(subject, str) or not subject.strip() or len(subject) > MAX_SUBJECT:
        return f"INVALID_INPUT: tiêu đề bắt buộc, tối đa {MAX_SUBJECT} ký tự"
    if any(c in s for s in (to, subject) for c in "\r\n"):
        return "INVALID_INPUT: không được có xuống dòng trong người nhận / tiêu đề"  # header injection
    if not isinstance(body, str) or not body.strip():
        return "INVALID_INPUT: nội dung bắt buộc"
    return None


def _config_error() -> str | None:
    missing = [k for k in ("SMTP_HOST", "SMTP_FROM_EMAIL") if not getattr(settings, k)]
    if settings.SMTP_USERNAME and not settings.SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if missing:
        return f"NOT_CONFIGURED: thiếu {', '.join(missing)} trong .env"
    if settings.SMTP_SECURITY not in ("starttls", "ssl", "none"):
        return "NOT_CONFIGURED: SMTP_SECURITY phải là starttls, ssl hoặc none"
    return None


def _build_message(to: str, subject: str, body: str, html: str | None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.SMTP_FROM_EMAIL.rpartition("@")[2] or None)
    msg.set_content(body)  # UTF-8 plain text (Vietnamese safe)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _login_once(server: smtplib.SMTP) -> None:
    """Authenticate with ONE mechanism (PLAIN, else LOGIN).

    smtplib's login() retries every advertised mechanism after a 535; Gmail drops the connection on the
    second attempt, so a wrong password surfaced as SMTPServerDisconnected instead of an auth error.
    """
    advertised = server.esmtp_features.get("auth", "").upper().split()
    mechanism = next((m for m in ("PLAIN", "LOGIN") if m in advertised), None)
    if mechanism is None:  # e.g. a CRAM-MD5-only server: let smtplib choose
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        return
    server.user, server.password = settings.SMTP_USERNAME, settings.SMTP_PASSWORD
    server.auth(mechanism, getattr(server, f"auth_{mechanism.lower()}"))


def _send_blocking(msg: EmailMessage, timeout: float) -> None:
    """Runs in a worker thread. Raises on any failure; the caller turns it into an EmailResult."""
    context = ssl.create_default_context()
    if settings.SMTP_SECURITY == "ssl":
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
    with server:
        server.ehlo()
        if settings.SMTP_SECURITY == "starttls":
            server.starttls(context=context)
            server.ehlo()
        if settings.SMTP_USERNAME:
            _login_once(server)
        refused = server.send_message(msg)
        if refused:  # some recipients refused but not all
            raise smtplib.SMTPRecipientsRefused(refused)


def _describe(exc: BaseException) -> str:
    """Error code + short reason. Never includes the password."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return f"SMTP_AUTH_FAILED: sai tên đăng nhập / mật khẩu SMTP ({exc.smtp_code})"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "RECIPIENT_REFUSED: máy chủ từ chối địa chỉ người nhận"
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return f"SENDER_REFUSED: máy chủ từ chối địa chỉ gửi ({exc.smtp_code})"
    if isinstance(exc, smtplib.SMTPResponseException):
        reply = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
        return f"SMTP_ERROR: {exc.smtp_code} {reply[:200]}"
    if isinstance(exc, (TimeoutError, socket.timeout, asyncio.TimeoutError)):
        return f"TIMEOUT: quá {settings.SMTP_TIMEOUT_SECONDS:g} giây"
    if isinstance(exc, ssl.SSLError):
        return f"TLS_ERROR: {exc.__class__.__name__} (kiểm tra SMTP_PORT / SMTP_SECURITY)"
    if isinstance(exc, (ConnectionError, socket.gaierror, OSError, smtplib.SMTPServerDisconnected)):
        return f"CONNECTION_FAILED: không kết nối được {settings.SMTP_HOST}:{settings.SMTP_PORT} ({exc.__class__.__name__})"
    return f"UNKNOWN_ERROR: {exc.__class__.__name__}"


async def send_email(to: str, subject: str, body: str, *, html: str | None = None) -> EmailResult:
    """Send one email. Always returns an EmailResult, never raises (see module docstring)."""
    try:
        error = _validate(to, subject, body) or _config_error()
        if error:
            logger.warning("EMAIL_FAILED to=%s error=%s", mask_email(str(to)), error.split(":")[0])
            return EmailResult(success=False, error=error)

        to = to.strip()
        msg = _build_message(to, subject.strip(), body, html)
        timeout = settings.SMTP_TIMEOUT_SECONDS
        # Socket timeout per step + one deadline for the whole conversation. If the deadline hits,
        # the worker thread is abandoned; its own socket timeout ends it shortly after.
        await asyncio.wait_for(run_in_threadpool(_send_blocking, msg, timeout), timeout=timeout)
        message_id = msg["Message-ID"]
        logger.info("EMAIL_SENT to=%s message_id=%s", mask_email(to), message_id)
        return EmailResult(success=True, provider_message_id=message_id)
    except Exception as exc:  # noqa: BLE001 - by contract no failure escapes (TimeoutError included).
        # asyncio.CancelledError (BaseException) is NOT caught: that is the caller's request being
        # cancelled, not an email failure, and swallowing it would break asyncio cancellation.
        error = _describe(exc)
        # ASCII-only log line: the error code + exception class (the Vietnamese detail is in the result)
        logger.warning("EMAIL_FAILED to=%s error=%s (%s)", mask_email(str(to)), error.split(":")[0], exc.__class__.__name__)
        return EmailResult(success=False, error=error)

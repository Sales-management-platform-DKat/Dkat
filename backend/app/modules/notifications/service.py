"""Pre-order notifications (FR-09.1 - FR-09.4). Contract: docs/api-contract.md.

    outcome = await notify_preorder(preorder_id, "PREORDER_READY")    # waits for the result
    schedule_notify_preorder(preorder_id, "PREORDER_READY")            # returns at once (fire-and-forget)

Channel rule: phone -> SMS first. If the SMS fails (rejected by eSMS, or accepted then refused by the
carrier, detected through the delivery status) and there is an email -> EMAIL. The last channel tried
is the final channel. One `notifications` row per attempt: inserted PENDING (committed), then updated
to SENT / FAILED with provider_message_id, error_message, sent_at.

Never raises and never touches the caller's transaction: it opens its own sessions. Call it AFTER the
caller has committed the pre-order change, otherwise it may read the old data.
"""
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.mailer import send_email
from app.core.sms import get_send_status, prepare_content, send_sms
from app.modules.notifications import repository
from app.modules.notifications.templates import EVENT_TYPES, ready_template_for, render, render_template
from app.utils.logger import get_logger

logger = get_logger("app.notifications")


@dataclass
class NotificationOutcome:
    preorder_id: int
    event_type: str
    status: str  # SENT (some channel succeeded) | FAILED | SKIPPED (nothing to send, no row written)
    final_channel: str | None = None  # SMS | EMAIL: the last channel tried
    notification_ids: list[int] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {
            "preorderId": d["preorder_id"], "eventType": d["event_type"], "status": d["status"],
            "finalChannel": d["final_channel"], "notificationIds": d["notification_ids"], "error": d["error"],
        }


async def _confirm_sms(sms_id: str) -> str | None:
    """Wait up to NOTIFY_SMS_CONFIRM_SECONDS for the carrier outcome. Returns an error when the carrier
    refused the SMS, None when it was delivered or is still pending at the deadline (counted as sent)."""
    deadline = settings.NOTIFY_SMS_CONFIRM_SECONDS
    waited = 0.0
    while waited < deadline:
        step = min(settings.NOTIFY_SMS_POLL_SECONDS, deadline - waited)
        await asyncio.sleep(step)
        waited += step
        status = await get_send_status(sms_id)
        if status["status"] == "DELIVERED":
            return None
        if status["status"] == "FAILED":
            return "CARRIER_REJECTED: nhà mạng không giao được tin (eSMS SendFailed)"
    return None


async def _deliver_sms(notification_id: int, phone: str, text: str, request_id: str) -> tuple[bool, str | None]:
    """Send an SMS for an existing PENDING row and record the result on it."""
    try:
        result = await send_sms(phone, text, request_id=request_id)
        error = result.error
        if result.success and result.provider_message_id and not settings.ESMS_SANDBOX:
            error = await _confirm_sms(result.provider_message_id)
        ok = result.success and error is None
        await repository.mark(notification_id, sent=ok, provider_message_id=result.provider_message_id, error=error)
        return ok, error
    except Exception as exc:  # noqa: BLE001 - keep the row consistent whatever happens
        error = f"UNKNOWN_ERROR: {exc.__class__.__name__}"
        await repository.mark(notification_id, sent=False, provider_message_id=None, error=error)
        return False, error


async def _deliver_email(
    notification_id: int, email: str, subject: str, body: str, html: str | None = None
) -> tuple[bool, str | None]:
    """Send an email for an existing PENDING row and record the result on it."""
    try:
        result = await send_email(email, subject, body, html=html)
        await repository.mark(notification_id, sent=result.success, provider_message_id=result.provider_message_id, error=result.error)
        return result.success, result.error
    except Exception as exc:  # noqa: BLE001
        error = f"UNKNOWN_ERROR: {exc.__class__.__name__}"
        await repository.mark(notification_id, sent=False, provider_message_id=None, error=error)
        return False, error


def _email_message(subject: str, body: str) -> str:
    """How an email is stored in notifications.message (split back by _split_email on resend)."""
    return f"{subject}\n\n{body}"


def _split_email(message: str) -> tuple[str, str]:
    subject, _, body = message.partition("\n\n")
    return subject, body


async def _try_sms(preorder_id: int, phone: str, text: str, event_type: str) -> tuple[int, bool, str | None]:
    sms_text, _ = prepare_content(text, settings.SMS_UNICODE)  # store exactly what is sent
    notification_id = await repository.insert_pending(preorder_id, "SMS", phone, sms_text or text, event_type)
    ok, error = await _deliver_sms(notification_id, phone, text, f"notification-{notification_id}")
    return notification_id, ok, error


async def _try_email(
    preorder_id: int, email: str, subject: str, body: str, event_type: str, html: str | None = None
) -> tuple[int, bool, str | None]:
    # the plain-text version is stored (a resend re-sends it as plain text)
    notification_id = await repository.insert_pending(preorder_id, "EMAIL", email, _email_message(subject, body), event_type)
    ok, error = await _deliver_email(notification_id, email, subject, body, html)
    return notification_id, ok, error


def hold_until_vn(preorder: dict) -> datetime:
    """Hold deadline in Vietnam time. expires_at is stored in UTC by the pre-order module
    (ready_at + PREORDER_READY_DAYS); when it is still NULL the same rule is applied here."""
    expires = preorder.get("expires_at")
    if expires is None:
        base = preorder.get("ready_at") or datetime.now(timezone.utc).replace(tzinfo=None)
        expires = base + timedelta(days=settings.PREORDER_READY_DAYS)
    return expires + timedelta(hours=7)


async def ready_template_data(preorder: dict) -> dict:
    """Data for templates.render_template from a loaded pre-order (+ its snapshot lines)."""
    return {
        "customer_name": preorder["customer_name"] or "",
        "preorder_code": preorder["code"],
        "branch_name": preorder["branch_name"],
        "branch_address": preorder["branch_address"],
        "contact_phone": preorder["branch_phone"] or settings.STORE_CONTACT_PHONE or None,
        "hold_until": hold_until_vn(preorder),
        "items": await repository.load_items(preorder["preorder_id"]),
        "total_amount": preorder["total_amount"],
    }


async def notify_preorder(preorder_id: int, event_type: str) -> NotificationOutcome:
    """Send the notification of `event_type` for one pre-order and record every attempt.

    event_type: PREORDER_CREATED | PREORDER_READY | PREORDER_CANCELLED | PREORDER_EXPIRED
    Never raises (failures are logged and recorded as FAILED rows).
    """
    outcome = NotificationOutcome(preorder_id=preorder_id, event_type=event_type, status="SKIPPED")
    try:
        if event_type not in EVENT_TYPES:
            outcome.error = f"UNKNOWN_EVENT: {event_type!r} (hợp lệ: {', '.join(EVENT_TYPES)})"
            return _log(outcome)
        preorder = await repository.load_preorder(preorder_id)
        if preorder is None:
            outcome.error = "PREORDER_NOT_FOUND"
            return _log(outcome)
        phone, email = (preorder["phone"] or "").strip(), (preorder["email"] or "").strip()
        if not phone and not email:
            outcome.error = "NO_CONTACT: đơn không có SĐT và email"
            return _log(outcome)

        html = None
        if event_type == "PREORDER_READY":  # FR-09.6: mẫu 1 (chưa thanh toán) / mẫu 2 (đã thanh toán)
            message = render_template(ready_template_for(preorder["payment_status"]), await ready_template_data(preorder))
            html = message.email_html
        else:
            message = render(event_type, preorder)
        errors: list[str] = []
        if phone:
            nid, ok, err = await _try_sms(preorder_id, phone, message.sms, event_type)
            outcome.notification_ids.append(nid)
            outcome.final_channel = "SMS"
            if ok:
                outcome.status = "SENT"
                return _log(outcome)
            errors.append(f"SMS {err}")
        if email:
            nid, ok, err = await _try_email(preorder_id, email, message.email_subject, message.email_body, event_type, html)
            outcome.notification_ids.append(nid)
            outcome.final_channel = "EMAIL"
            if ok:
                outcome.status = "SENT"
                outcome.error = "; ".join(errors) or None  # keep why the SMS fell back to email
                return _log(outcome)
            errors.append(f"EMAIL {err}")
        outcome.status = "FAILED"
        outcome.error = "; ".join(errors)
        return _log(outcome)
    except Exception as exc:  # noqa: BLE001 - e.g. database unavailable
        outcome.status = "FAILED"
        outcome.error = f"INTERNAL_ERROR: {exc.__class__.__name__}"
        logger.exception("NOTIFY_PREORDER_CRASH preorder_id=%s event=%s", preorder_id, event_type)
        return outcome


def _log(o: NotificationOutcome) -> NotificationOutcome:
    level = logger.info if o.status == "SENT" else logger.warning
    # ids and codes only: no phone, email or message text in the log
    level(
        "NOTIFY_PREORDER preorder_id=%s event=%s status=%s channel=%s ids=%s error=%s",
        o.preorder_id, o.event_type, o.status, o.final_channel, o.notification_ids,
        (o.error or "").split(":")[0][:60] or None,
    )
    return o


# --------------------------------------------------------------------------- fire-and-forget

_background: set[asyncio.Task] = set()  # strong references: otherwise a running task may be garbage-collected


def _spawn(preorder_id: int, event_type: str) -> None:
    task = asyncio.get_running_loop().create_task(notify_preorder(preorder_id, event_type))
    _background.add(task)
    task.add_done_callback(_background.discard)


def schedule_notify_preorder(preorder_id: int, event_type: str) -> None:
    """Start notify_preorder in the background and return immediately. Never raises.

    - async code (event loop thread): creates a task.
    - sync code running in FastAPI's thread pool (`def` routes, run_in_threadpool): hands the task
      to the event loop through anyio.from_thread.
    - plain scripts without any event loop: runs it to completion (blocking), there is no loop to defer to.
    """
    try:
        asyncio.get_running_loop()
        _spawn(preorder_id, event_type)
        return
    except RuntimeError:
        pass  # no loop in this thread
    try:
        import anyio.from_thread

        anyio.from_thread.run_sync(_spawn, preorder_id, event_type)
        return
    except RuntimeError:
        pass  # not an anyio worker thread
    try:
        asyncio.run(notify_preorder(preorder_id, event_type))
    except Exception:  # noqa: BLE001
        logger.exception("NOTIFY_SCHEDULE_FAILED preorder_id=%s event=%s", preorder_id, event_type)


async def wait_for_background() -> None:
    """Wait for scheduled notifications (tests / graceful shutdown)."""
    if _background:
        await asyncio.gather(*list(_background), return_exceptions=True)


# --------------------------------------------------------------------------- facade (contract with the pre-order module)


def _outcome_dict(preorder_id: int, event_type: str, status: str, error: str | None) -> dict:
    return NotificationOutcome(preorder_id=preorder_id, event_type=event_type, status=status, error=error).to_dict()


class NotificationService:
    """Entry point used by the pre-order module (docs/api-contract.md). Every method never raises.

    NotificationService.notifyPreorder(preorder_id, "PREORDER_READY") -> dict
        For SYNC callers (`def` routes running in FastAPI's thread pool, scripts, worker processes):
        runs the whole send and returns the outcome dict, so the caller can rely on the
        `notifications` rows right after (e.g. set the pre-order to NOTIFIED when status == "SENT").
        Blocks only the calling worker thread, never the event loop. If it is called from the event
        loop thread itself it cannot wait: it schedules the send and returns status "SCHEDULED".
    await NotificationService.notifyPreorderAsync(preorder_id, event_type) -> NotificationOutcome
        For async callers that want the result.
    NotificationService.schedulePreorder(preorder_id, event_type) -> None
        Fire-and-forget from anywhere (does not wait for the result).
    """

    EVENT_TYPES = EVENT_TYPES

    @staticmethod
    def notifyPreorder(preorder_id: int, event_type: str) -> dict:  # noqa: N802 - name fixed by the contract
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:  # inside the event loop thread: blocking here would freeze the whole server
            schedule_notify_preorder(preorder_id, event_type)
            return _outcome_dict(preorder_id, event_type, "SCHEDULED", None)
        try:
            import anyio.from_thread

            try:  # FastAPI / Starlette worker thread: run on the app's event loop and wait
                return anyio.from_thread.run(notify_preorder, preorder_id, event_type).to_dict()
            except RuntimeError:
                pass  # not an anyio worker thread
            # plain script / separate worker process: no app loop, use a private one
            return asyncio.run(notify_preorder(preorder_id, event_type)).to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.exception("NOTIFY_PREORDER_SYNC_FAILED preorder_id=%s event=%s", preorder_id, event_type)
            return _outcome_dict(preorder_id, event_type, "FAILED", f"INTERNAL_ERROR: {exc.__class__.__name__}")

    notifyPreorderAsync = staticmethod(notify_preorder)  # noqa: N815
    schedulePreorder = staticmethod(schedule_notify_preorder)  # noqa: N815

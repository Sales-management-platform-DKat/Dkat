"""Retry of FAILED notifications (FR-09.5, NFR-10).

- resend_notification(id, automatic=False): staff "Gửi lại" button (POST /notifications/{id}/resend).
- retry_failed_notifications(): one pass of the automatic job; run_retry_loop() runs it every
  NOTIFY_RETRY_INTERVAL_SECONDS (5 min), started with the app (main.py lifespan).

A resend re-sends the SAME row (same channel, recipient and stored message) and increments
retry_count on it. The row is first claimed atomically (FAILED -> PENDING), so the job and a staff
click, or two clicks, can never send the same row twice. After NOTIFY_MAX_RETRIES failed re-sends the
row stays FAILED with a RETRY_EXHAUSTED reason; staff can still resend it by hand.

The automatic job does NOT retry:
- permanent errors (PERMANENT_ERROR_CODES): the same content to the same recipient cannot succeed;
- a failed row when the customer was reached later for the same pre-order (a later SENT row,
  e.g. the email fallback worked): retrying would notify twice.
"""
import asyncio
import logging

from app.core.config import settings
from app.modules.notifications import repository
from app.modules.notifications.service import _deliver_email, _deliver_sms, _split_email
from app.utils.logger import get_logger

logger = get_logger("app.notifications.retry")

PERMANENT_ERROR_CODES = (
    "INVALID_INPUT", "INVALID_PHONE", "TEMPLATE_MISMATCH", "BRANDNAME_INVALID", "CARRIER_NOT_REGISTERED",
    "CARRIER_REJECTED", "BLOCKED_KEYWORD", "PHONE_BLOCKED", "UNSUPPORTED_TYPE", "RECIPIENT_REFUSED",
)


async def resend_notification(notification_id: int, *, automatic: bool = False) -> dict:
    """Re-send one FAILED notification. Never raises.

    Returns {"result": "SENT" | "FAILED" | "NOT_FOUND" | "NOT_FAILED" | "LIMIT_REACHED", "notification": row|None}
    NOT_FAILED: the row is SENT, or PENDING because someone else is sending it right now.
    """
    try:
        row = await repository.get_notification(notification_id)
        if row is None:
            return {"result": "NOT_FOUND", "notification": None}
        max_retries = settings.NOTIFY_MAX_RETRIES if automatic else None  # staff may go beyond the limit
        if not await repository.claim_for_resend(notification_id, max_retries=max_retries):
            current = await repository.get_notification(notification_id)
            limit_hit = current and current["status"] == "FAILED" and automatic
            return {"result": "LIMIT_REACHED" if limit_hit else "NOT_FAILED", "notification": current}

        attempt = row["retry_count"] + 1
        if row["channel"] == "SMS":
            # a new RequestId per attempt: eSMS rejects a RequestId already used in the last 24 h
            ok, error = await _deliver_sms(notification_id, row["recipient"], row["message"], f"notification-{notification_id}-r{attempt}")
        else:
            subject, body = _split_email(row["message"])
            ok, error = await _deliver_email(notification_id, row["recipient"], subject, body)

        if not ok and attempt >= settings.NOTIFY_MAX_RETRIES:
            error = f"RETRY_EXHAUSTED: đã gửi lại {attempt} lần vẫn lỗi, dừng tự động. Lỗi cuối: {error}"
            await repository.set_error(notification_id, error)
        logger.log(
            logging.INFO if ok else logging.WARNING,
            "NOTIFY_RESEND id=%s attempt=%s automatic=%s result=%s error=%s",
            notification_id, attempt, automatic, "SENT" if ok else "FAILED", (error or "").split(":")[0] or None,
        )
        return {"result": "SENT" if ok else "FAILED", "notification": await repository.get_notification(notification_id)}
    except Exception:  # noqa: BLE001
        logger.exception("NOTIFY_RESEND_CRASH id=%s", notification_id)
        return {"result": "FAILED", "notification": None}


async def retry_failed_notifications(limit: int | None = None) -> dict:
    """One pass of the automatic job. Returns {"checked", "sent", "failed", "skipped"}."""
    summary = {"checked": 0, "sent": 0, "failed": 0, "skipped": 0}
    try:
        ids = await repository.auto_retry_candidates(
            settings.NOTIFY_MAX_RETRIES, PERMANENT_ERROR_CODES, limit or settings.NOTIFY_RETRY_BATCH
        )
    except Exception:  # noqa: BLE001 - e.g. database down: try again next run
        logger.exception("NOTIFY_RETRY_SCAN_FAILED")
        return summary
    for notification_id in ids:
        summary["checked"] += 1
        outcome = await resend_notification(notification_id, automatic=True)
        key = {"SENT": "sent", "FAILED": "failed"}.get(outcome["result"], "skipped")
        summary[key] += 1
    if ids:
        logger.info("NOTIFY_RETRY_RUN %s", summary)
    return summary


async def run_retry_loop() -> None:
    """Forever: wait NOTIFY_RETRY_INTERVAL_SECONDS, then one retry pass. Cancelled on shutdown."""
    while True:
        await asyncio.sleep(settings.NOTIFY_RETRY_INTERVAL_SECONDS)
        await retry_failed_notifications()

"""SQL for pre-order notifications (table `notifications`, one row per send attempt).

Every write commits right away in its own transaction, so the trail survives even if the caller's
transaction or the send itself fails. The functions are async (the notification service awaits them)
but run the synchronous engine in a worker thread, so they never block the event loop.
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.session import engine

COLUMNS = """n.notification_id, n.preorder_id, n.event_type, n.channel, n.recipient, n.message, n.status,
             n.retry_count, n.provider_message_id, n.error_message, n.sent_at, n.last_attempt_at, n.created_at"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _one(sql: str, params: dict) -> dict | None:
    with engine.connect() as db:
        row = db.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def _all(sql: str, params: dict) -> list[dict]:
    with engine.connect() as db:
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


def _write(sql: str, params: dict) -> int:
    """Run one statement in its own committed transaction. Returns rowcount (lastrowid for INSERT)."""
    with engine.begin() as db:
        result = db.execute(text(sql), params)
        return result.lastrowid if sql.lstrip().upper().startswith("INSERT") else result.rowcount


async def load_preorder(preorder_id: int) -> dict | None:
    return await asyncio.to_thread(_one, """
        SELECT p.preorder_id, p.preorder_code AS code, p.customer_name, p.customer_phone AS phone,
               p.customer_email AS email, p.total_amount, p.status, p.branch_id, b.store_id,
               p.payment_status, p.ready_at, p.expires_at,
               b.name AS branch_name, b.address AS branch_address, b.phone AS branch_phone
        FROM preorders p JOIN branches b ON b.branch_id = p.branch_id
        WHERE p.preorder_id = :id""", {"id": preorder_id})


async def insert_pending(preorder_id: int, channel: str, recipient: str, message: str, event_type: str | None) -> int:
    return await asyncio.to_thread(_write, """
        INSERT INTO notifications (preorder_id, channel, recipient, message, status, event_type, retry_count, last_attempt_at)
        VALUES (:p, :channel, :recipient, :message, 'PENDING', :event, 0, :at)""",
        {"p": preorder_id, "channel": channel, "recipient": recipient, "message": message,
         "event": event_type, "at": utc_now()})


async def mark(notification_id: int, *, sent: bool, provider_message_id: str | None, error: str | None) -> None:
    # sent_at in UTC like every other *_at written by the services; NULL when nothing was sent
    await asyncio.to_thread(_write, """
        UPDATE notifications SET status = :status, provider_message_id = :pmid, error_message = :error, sent_at = :sent_at
        WHERE notification_id = :id""",
        {"id": notification_id, "status": "SENT" if sent else "FAILED", "pmid": provider_message_id,
         "error": error, "sent_at": utc_now() if sent else None})


async def get_notification(notification_id: int) -> dict | None:
    """The row plus the branch / store of its pre-order (for permission checks)."""
    return await asyncio.to_thread(_one, f"""
        SELECT {COLUMNS}, p.branch_id, b.store_id
        FROM notifications n JOIN preorders p ON p.preorder_id = n.preorder_id
        JOIN branches b ON b.branch_id = p.branch_id
        WHERE n.notification_id = :id""", {"id": notification_id})


async def list_for_preorder(preorder_id: int) -> list[dict]:
    return await asyncio.to_thread(_all, f"SELECT {COLUMNS} FROM notifications n WHERE n.preorder_id = :p ORDER BY n.notification_id",
                                   {"p": preorder_id})


async def claim_for_resend(notification_id: int, *, max_retries: int | None) -> bool:
    """Atomically move one FAILED row to PENDING and count the attempt (retry_count + 1).

    Only one caller can win (job vs. a staff click, or two clicks): the others get False and must
    not send. max_retries=None (manual resend) ignores the limit.
    """
    limit = "" if max_retries is None else " AND retry_count < :max"
    changed = await asyncio.to_thread(_write, f"""
        UPDATE notifications SET status = 'PENDING', retry_count = retry_count + 1, last_attempt_at = :at
        WHERE notification_id = :id AND status = 'FAILED'{limit}""",
        {"id": notification_id, "at": utc_now(), "max": max_retries})
    return changed == 1


async def auto_retry_candidates(max_retries: int, permanent_codes: tuple[str, ...], limit: int) -> list[int]:
    """FAILED rows the job may re-send: fewer than `max_retries` re-sends, error not permanent, and the
    customer was NOT reached later for this pre-order (e.g. SMS failed but the email fallback was SENT)."""
    not_permanent = " AND ".join(f"n.error_message NOT LIKE '{code}:%'" for code in permanent_codes) or "1 = 1"
    rows = await asyncio.to_thread(_all, f"""
        SELECT n.notification_id FROM notifications n
        WHERE n.status = 'FAILED' AND n.retry_count < :max
          AND (n.error_message IS NULL OR ({not_permanent}))
          AND NOT EXISTS (SELECT 1 FROM notifications s
                          WHERE s.preorder_id = n.preorder_id AND s.status = 'SENT'
                            AND s.notification_id > n.notification_id)
        ORDER BY n.notification_id LIMIT :limit""", {"max": max_retries, "limit": limit})
    return [r["notification_id"] for r in rows]


async def mark_preorder_notified(preorder_id: int) -> None:
    """READY -> NOTIFIED once a notification reached the customer. Only a still-READY order changes:
    an order fulfilled, cancelled or expired in the meantime keeps its status."""
    await asyncio.to_thread(_write, "UPDATE preorders SET status = 'NOTIFIED' WHERE preorder_id = :id AND status = 'READY'",
                            {"id": preorder_id})


async def set_error(notification_id: int, error: str) -> None:
    await asyncio.to_thread(_write, "UPDATE notifications SET error_message = :e WHERE notification_id = :id",
                            {"id": notification_id, "e": error})


async def load_items(preorder_id: int) -> list[dict]:
    """Snapshot lines of the pre-order (name / SKU / price at order time)."""
    return await asyncio.to_thread(_all, """
        SELECT product_name_snapshot AS name, sku_snapshot AS sku, quantity, unit_price, line_total
        FROM preorder_items WHERE preorder_id = :p ORDER BY preorder_item_id""", {"p": preorder_id})

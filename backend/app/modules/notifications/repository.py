"""SQL for pre-order notifications. Every write is committed right away (own session), so the trail
survives even if the caller's transaction or the send itself fails."""
from datetime import datetime, timezone

from sqlalchemy import text, update

from app.db.session import standalone_transaction
from app.modules.notifications.models import Notification

COLUMNS = """n.notification_id, n.preorder_id, n.event_type, n.channel, n.recipient, n.message, n.status,
             n.retry_count, n.provider_message_id, n.error_message, n.sent_at, n.last_attempt_at, n.created_at"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


async def load_preorder(preorder_id: int) -> dict | None:
    async with standalone_transaction() as db:
        row = (
            await db.execute(
                text(
                    """SELECT p.preorder_id, p.preorder_code AS code, p.customer_name, p.customer_phone AS phone,
                              p.customer_email AS email, p.total_amount, p.status, p.branch_id, b.store_id,
                              p.payment_status, p.ready_at, p.expires_at,
                              b.name AS branch_name, b.address AS branch_address, b.phone AS branch_phone
                       FROM preorders p JOIN branches b ON b.branch_id = p.branch_id
                       WHERE p.preorder_id = :id"""
                ),
                {"id": preorder_id},
            )
        ).mappings().first()
    return dict(row) if row else None


async def insert_pending(preorder_id: int, channel: str, recipient: str, message: str, event_type: str | None) -> int:
    async with standalone_transaction() as db:
        row = Notification(
            preorder_id=preorder_id, channel=channel, recipient=recipient, message=message, status="PENDING",
            event_type=event_type, retry_count=0, last_attempt_at=utc_now(),
        )
        db.add(row)
        await db.flush()
        return row.notification_id


async def mark(notification_id: int, *, sent: bool, provider_message_id: str | None, error: str | None) -> None:
    values = {
        "status": "SENT" if sent else "FAILED",
        "provider_message_id": provider_message_id,
        "error_message": error,
        # UTC like every other *_at written by the services; NULL when nothing was sent
        "sent_at": utc_now() if sent else None,
    }
    async with standalone_transaction() as db:
        await db.execute(update(Notification).where(Notification.notification_id == notification_id).values(**values))


async def get_notification(notification_id: int) -> dict | None:
    """The row plus the branch / store of its pre-order (for permission checks)."""
    async with standalone_transaction() as db:
        row = (
            await db.execute(
                text(
                    f"""SELECT {COLUMNS}, p.branch_id, b.store_id
                        FROM notifications n JOIN preorders p ON p.preorder_id = n.preorder_id
                        JOIN branches b ON b.branch_id = p.branch_id
                        WHERE n.notification_id = :id"""
                ),
                {"id": notification_id},
            )
        ).mappings().first()
    return dict(row) if row else None


async def list_for_preorder(preorder_id: int) -> list[dict]:
    async with standalone_transaction() as db:
        rows = (
            await db.execute(
                text(f"SELECT {COLUMNS} FROM notifications n WHERE n.preorder_id = :p ORDER BY n.notification_id"),
                {"p": preorder_id},
            )
        ).mappings().all()
    return [dict(r) for r in rows]


async def claim_for_resend(notification_id: int, *, max_retries: int | None) -> bool:
    """Atomically move one FAILED row to PENDING and count the attempt (retry_count + 1).

    Only one caller can win (job vs. a staff click, or two clicks): the others get False and must
    not send. max_retries=None (manual resend) ignores the limit.
    """
    limit = "" if max_retries is None else " AND retry_count < :max"
    async with standalone_transaction() as db:
        result = await db.execute(
            text(
                f"""UPDATE notifications SET status = 'PENDING', retry_count = retry_count + 1, last_attempt_at = :at
                    WHERE notification_id = :id AND status = 'FAILED'{limit}"""
            ),
            {"id": notification_id, "at": utc_now(), "max": max_retries},
        )
    return result.rowcount == 1


async def auto_retry_candidates(max_retries: int, permanent_codes: tuple[str, ...], limit: int) -> list[int]:
    """FAILED rows the job may re-send:
    - fewer than `max_retries` re-sends so far;
    - the error is not a permanent one (resending the same content cannot work);
    - the customer was NOT reached later for this pre-order (no SENT row after it), e.g. the SMS
      failed but the email fallback succeeded: resending the SMS would notify twice.
    """
    not_permanent = " AND ".join(f"n.error_message NOT LIKE '{code}:%'" for code in permanent_codes) or "1 = 1"
    async with standalone_transaction() as db:
        rows = await db.execute(
            text(
                f"""SELECT n.notification_id FROM notifications n
                    WHERE n.status = 'FAILED' AND n.retry_count < :max
                      AND (n.error_message IS NULL OR ({not_permanent}))
                      AND NOT EXISTS (SELECT 1 FROM notifications s
                                      WHERE s.preorder_id = n.preorder_id AND s.status = 'SENT'
                                        AND s.notification_id > n.notification_id)
                    ORDER BY n.notification_id LIMIT :limit"""
            ),
            {"max": max_retries, "limit": limit},
        )
        return list(rows.scalars())


async def set_error(notification_id: int, error: str) -> None:
    async with standalone_transaction() as db:
        await db.execute(update(Notification).where(Notification.notification_id == notification_id).values(error_message=error))


async def load_items(preorder_id: int) -> list[dict]:
    """Snapshot lines of the pre-order (name / SKU / price at order time)."""
    async with standalone_transaction() as db:
        rows = (
            await db.execute(
                text(
                    """SELECT product_name_snapshot AS name, sku_snapshot AS sku, quantity, unit_price, line_total
                       FROM preorder_items WHERE preorder_id = :p ORDER BY preorder_item_id"""
                ),
                {"p": preorder_id},
            )
        ).mappings().all()
    return [dict(r) for r in rows]

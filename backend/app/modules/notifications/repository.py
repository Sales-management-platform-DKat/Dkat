"""SQL for pre-order notifications. Every write is committed right away (own session), so the trail
survives even if the caller's transaction or the send itself fails."""
from datetime import datetime, timezone

from sqlalchemy import text, update

from app.db.session import standalone_transaction
from app.modules.notifications.models import Notification


async def load_preorder(preorder_id: int) -> dict | None:
    async with standalone_transaction() as db:
        row = (
            await db.execute(
                text(
                    """SELECT p.preorder_id, p.preorder_code AS code, p.customer_name, p.customer_phone AS phone,
                              p.customer_email AS email, p.total_amount, p.status,
                              b.name AS branch_name, b.address AS branch_address, b.phone AS branch_phone
                       FROM preorders p JOIN branches b ON b.branch_id = p.branch_id
                       WHERE p.preorder_id = :id"""
                ),
                {"id": preorder_id},
            )
        ).mappings().first()
    return dict(row) if row else None


async def insert_pending(preorder_id: int, channel: str, recipient: str, message: str) -> int:
    async with standalone_transaction() as db:
        row = Notification(preorder_id=preorder_id, channel=channel, recipient=recipient, message=message, status="PENDING")
        db.add(row)
        await db.flush()
        return row.notification_id


async def mark(notification_id: int, *, sent: bool, provider_message_id: str | None, error: str | None) -> None:
    values = {
        "status": "SENT" if sent else "FAILED",
        "provider_message_id": provider_message_id,
        "error_message": error,
        # UTC like every other *_at written by the services; NULL when nothing was sent
        "sent_at": datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) if sent else None,
    }
    async with standalone_transaction() as db:
        await db.execute(update(Notification).where(Notification.notification_id == notification_id).values(**values))

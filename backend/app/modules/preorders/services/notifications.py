import logging

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


def notify_ready_preorders(ready_ids: list[int]) -> None:
    """Dispatch notifications after the transaction that made these orders READY has committed."""
    if not ready_ids:
        return

    try:
        from app.modules.notifications.service import NotificationService
    except Exception as exc:
        logger.warning("NotificationService unavailable for %s ready preorders (%s)", len(ready_ids), type(exc).__name__)
        return

    for preorder_id in ready_ids:
        # The service owns delivery and commits its notification records independently.
        try:
            NotificationService.notifyPreorder(preorder_id, "PREORDER_READY")
        except Exception as exc:
            logger.warning("PREORDER_READY delivery failed for preorder %s (%s)", preorder_id, type(exc).__name__)

        # A channel can succeed before another raises. Only update still-READY orders.
        try:
            with engine.begin() as db:
                db.execute(text("""
                    UPDATE preorders SET status='NOTIFIED'
                    WHERE preorder_id=:id AND status='READY'
                      AND EXISTS (
                          SELECT 1 FROM notifications WHERE preorder_id=:id AND status='SENT'
                      )
                """), {"id": preorder_id})
        except Exception:
            logger.exception("Could not reconcile notification status for preorder %s", preorder_id)

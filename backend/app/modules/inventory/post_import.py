import logging

from sqlalchemy import text

from app.db.session import engine
from app.modules.preorders.services.allocation import allocate_imported_preorders

logger = logging.getLogger(__name__)


def process_committed_stock_import(branch_id: int, variant_ids: list[int]) -> None:
    """Allocate and notify after the stock import (JSON or CSV) has committed."""
    try:
        ready_ids = allocate_imported_preorders(branch_id, variant_ids)
    except Exception:
        logger.exception("Preorder allocation failed after import committed for branch %s", branch_id)
        return

    if not ready_ids:
        return

    try:
        from app.modules.notifications.service import NotificationService
    except Exception as exc:
        logger.warning("NotificationService unavailable for branch %s (%s)", branch_id, type(exc).__name__)
        return

    for preorder_id in ready_ids:
        # The service owns delivery and commits its notification records independently.
        try:
            NotificationService.notifyPreorder(preorder_id, "PREORDER_READY")
        except Exception as exc:
            logger.warning("PREORDER_READY delivery failed for preorder %s (%s)", preorder_id, type(exc).__name__)

        # A channel can succeed before another raises. Use committed delivery statuses
        # and update only a still-READY order, even if delivery took a long time.
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

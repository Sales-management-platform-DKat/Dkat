from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor
from app.modules.inventory.service import lock_inventory_rows
from app.modules.preorders.schemas import PreorderDetail
from app.modules.preorders.services.allocation import allocate_locked_variants
from app.modules.preorders.services.queries import get_preorder, get_preorder_branch, get_preorder_variant_ids


def release_reservations(db: Connection, branch_id: int, preorder_id: int) -> list[int]:
    """Release and reallocate with the order and its inventory already locked."""
    params = {"id": preorder_id}
    variants = list(db.execute(text("""
        SELECT DISTINCT variant_id FROM preorder_items WHERE preorder_id=:id AND allocated_quantity>0
    """), params).scalars())
    if not variants:
        return []
    db.execute(text("UPDATE preorder_items SET allocated_quantity=0 WHERE preorder_id=:id AND allocated_quantity>0"), params)
    return allocate_locked_variants(db, branch_id, variants)


def cancel_preorder(db: Connection, actor: Actor, preorder_id: int, reason: str) -> tuple[PreorderDetail, list[int]]:
    branch_id = get_preorder_branch(db, actor, preorder_id)
    lock_inventory_rows(db, branch_id, get_preorder_variant_ids(db, preorder_id), create_missing=False)
    order = get_preorder(db, actor, preorder_id, lock=True)
    if order.status in {"CANCELLED", "FULFILLED"} or (order.fulfillment and order.fulfillment.status == "COMPLETED"):
        raise HTTPException(409, {"code": "PREORDER_NOT_CANCELLABLE"})

    if order.paymentStatus == "PAID":
        db.execute(text("""
            UPDATE payments SET status='REFUNDED' WHERE preorder_id=:id AND status='SUCCESS'
        """), {"id": preorder_id})
    db.execute(text("""
        UPDATE preorders SET status='CANCELLED', cancel_reason=:reason, cancelled_at=UTC_TIMESTAMP(),
            payment_status=CASE WHEN payment_status='PAID' THEN 'REFUNDED' ELSE payment_status END
        WHERE preorder_id=:id
    """), {"id": preorder_id, "reason": reason})
    ready_ids = release_reservations(db, branch_id, preorder_id)
    return get_preorder(db, actor, preorder_id), ready_ids


def expire_preorder(db: Connection, branch_id: int, preorder_id: int, cutoff: datetime) -> list[int] | None:
    lock_inventory_rows(db, branch_id, get_preorder_variant_ids(db, preorder_id), create_missing=False)
    # Recheck after acquiring inventory, since fulfillment, cancellation or another worker may have won.
    expired = db.execute(text("""
        UPDATE preorders SET status='EXPIRED'
        WHERE preorder_id=:id AND branch_id=:branch AND status IN ('READY','NOTIFIED') AND expires_at < :cutoff
    """), {"id": preorder_id, "branch": branch_id, "cutoff": cutoff})
    if not expired.rowcount:
        return None
    return release_reservations(db, branch_id, preorder_id)

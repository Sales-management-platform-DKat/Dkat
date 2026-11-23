from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor
from app.modules.inventory.service import lock_inventory_rows, record_movement, reserved_quantities
from app.modules.preorders.schemas import FulfillmentInput, PreorderDetail
from app.modules.preorders.services.payment import ensure_preorder_unpaid, record_preorder_payment
from app.modules.preorders.services.queries import get_preorder, get_preorder_branch
from app.modules.sales.schemas import PaymentMethod

READY_STATUSES = {"READY", "NOTIFIED"}


def check_fulfillment_state(order: PreorderDetail, now: datetime, allowed_statuses: set[str]) -> None:
    if order.status not in allowed_statuses or (order.fulfillment and order.fulfillment.status == "COMPLETED"):
        raise HTTPException(409, {"code": "PREORDER_NOT_FULFILLABLE"})
    if order.expiresAt is not None and now.replace(tzinfo=timezone.utc) >= order.expiresAt:
        raise HTTPException(409, {"code": "PREORDER_EXPIRED"})


def set_preorder_fulfillment(
    db: Connection, actor: Actor, preorder_id: int, data: FulfillmentInput,
) -> PreorderDetail:
    order = get_preorder(db, actor, preorder_id, lock=True)
    now = db.execute(text("SELECT UTC_TIMESTAMP()")).scalar_one()
    check_fulfillment_state(order, now, READY_STATUSES | {"WAITING_STOCK"})

    address = None
    if data.method == "DELIVERY":
        address = data.deliveryAddress or (order.customer.address or "").strip()
        if not address:
            raise HTTPException(422, {"code": "DELIVERY_ADDRESS_REQUIRED"})
    db.execute(text("""
        INSERT INTO preorder_fulfillments (preorder_id, fulfillment_method, delivery_address, status)
        VALUES (:id, :method, :address, 'PENDING')
        ON DUPLICATE KEY UPDATE fulfillment_method=:method, delivery_address=:address
    """), {"id": preorder_id, "method": data.method, "address": address})
    return get_preorder(db, actor, preorder_id)


def fulfill_preorder(
    db: Connection, actor: Actor, preorder_id: int, payment_method: PaymentMethod | None,
) -> PreorderDetail:
    branch_id = get_preorder_branch(db, actor, preorder_id)
    # Item identities are immutable after creation. Acquire inventory before the parent,
    # matching FIFO and the other reservation writers.
    variant_ids = list(db.execute(text("""
        SELECT DISTINCT variant_id FROM preorder_items WHERE preorder_id=:id
    """), {"id": preorder_id}).scalars())
    stock = lock_inventory_rows(db, branch_id, variant_ids, create_missing=False)
    order = get_preorder(db, actor, preorder_id, lock=True)
    now = db.execute(text("SELECT UTC_TIMESTAMP()")).scalar_one()
    check_fulfillment_state(order, now, READY_STATUSES)
    if not order.items or any(item.allocatedQuantity != item.quantity for item in order.items):
        raise HTTPException(409, {"code": "PREORDER_NOT_FULLY_ALLOCATED"})

    required: dict[int, int] = {}
    for item in order.items:
        required[item.variantId] = required.get(item.variantId, 0) + item.quantity
    reserved = reserved_quantities(db, branch_id, list(required))
    for variant_id, quantity in required.items():
        if variant_id not in stock or stock[variant_id][1] < max(quantity, reserved.get(variant_id, 0)):
            raise HTTPException(409, {"code": "INSUFFICIENT_STOCK", "variantId": variant_id})

    if order.paymentStatus != "PAID":
        ensure_preorder_unpaid(order)
        if payment_method is None:
            raise HTTPException(422, {"code": "PAYMENT_METHOD_REQUIRED"})
        record_preorder_payment(db, actor, order, payment_method, now)

    for variant_id in sorted(required):
        inventory_id, before = stock[variant_id]
        record_movement(
            db, actor, variant_id=variant_id, inventory_id=inventory_id, before=before,
            after=before - required[variant_id], movement_type="PREORDER_FULFILLMENT",
            note=f"Giao đơn {order.preorderCode}", reference_type="PREORDER", reference_id=preorder_id,
        )
    db.execute(text("UPDATE preorder_items SET allocated_quantity=0 WHERE preorder_id=:id"), {"id": preorder_id})
    # An existing selection keeps its method and address. Orders without a selection use pickup.
    db.execute(text("""
        INSERT INTO preorder_fulfillments (preorder_id, fulfillment_method, status, confirmed_by, completed_at)
        VALUES (:id, 'PICKUP', 'COMPLETED', :user, :at)
        ON DUPLICATE KEY UPDATE status='COMPLETED', confirmed_by=:user, completed_at=:at
    """), {"id": preorder_id, "user": actor.user_id, "at": now})
    db.execute(text("""
        UPDATE preorders SET status='FULFILLED', fulfilled_at=:at WHERE preorder_id=:id
    """), {"id": preorder_id, "at": now})
    return get_preorder(db, actor, preorder_id)

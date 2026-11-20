from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor
from app.modules.preorders.schemas import PreorderDetail
from app.modules.preorders.services.queries import get_preorder
from app.modules.sales.schemas import ConfirmPaymentInput

PAYABLE_STATUSES = {"WAITING_STOCK", "READY", "NOTIFIED"}


def confirm_preorder_payment(
    db: Connection, actor: Actor, preorder_id: int, data: ConfirmPaymentInput,
) -> PreorderDetail:
    order = get_preorder(db, actor, preorder_id, lock=True)
    if order.status not in PAYABLE_STATUSES:
        raise HTTPException(409, {"code": "PREORDER_NOT_PAYABLE"})
    if order.paymentStatus != "UNPAID" or any(payment.status == "SUCCESS" for payment in order.payments):
        raise HTTPException(409, {"code": "PREORDER_ALREADY_PAID"})
    if data.amount != order.totalAmount:
        raise HTTPException(422, {"code": "PAYMENT_AMOUNT_MISMATCH", "expectedAmount": str(order.totalAmount)})
    confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    db.execute(text("""
        INSERT INTO payments (preorder_id,payment_method,amount,status,confirmed_by,confirmed_at)
        VALUES (:order,:method,:amount,'SUCCESS',:user,:at)
    """), {"order": preorder_id, "method": data.paymentMethod, "amount": data.amount,
           "user": actor.user_id, "at": confirmed_at})
    db.execute(text("UPDATE preorders SET payment_status='PAID' WHERE preorder_id=:id"), {"id": preorder_id})
    return get_preorder(db, actor, preorder_id)

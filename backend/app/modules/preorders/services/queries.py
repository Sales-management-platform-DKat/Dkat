from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor, get_accessible_branch_ids, require_branch_access
from app.modules.customers.service import normalize_phone
from app.modules.preorders.schemas import (
    PreorderDetail, PreorderFilters, PreorderFulfillment, PreorderLine,
    PreorderNotification, PreorderSummary, StoredPreorderCustomer,
)
from app.modules.sales.schemas import OrderPayment

HEADER_SELECT = """
    SELECT p.preorder_id AS preorderId, p.preorder_code AS preorderCode,
           p.branch_id AS branchId, b.name AS branchName, p.customer_id AS customerId,
           p.customer_name AS customerName, p.customer_phone AS customerPhone,
           p.customer_email AS customerEmail, p.customer_address AS customerAddress,
           p.total_amount AS totalAmount, p.status, p.payment_status AS paymentStatus,
           p.note, p.created_at AS createdAt, p.ready_at AS readyAt,
           p.expires_at AS expiresAt, p.fulfilled_at AS fulfilledAt
    FROM preorders AS p
    JOIN branches AS b ON b.branch_id=p.branch_id AND b.store_id=:store
"""


def summary_from_row(row) -> PreorderSummary:
    fields = dict(row)
    customer = StoredPreorderCustomer(fullName=fields.pop("customerName"), phone=fields.pop("customerPhone"),
                                     email=fields.pop("customerEmail"), address=fields.pop("customerAddress"))
    return PreorderSummary(**fields, customer=customer)


def load_items(db: Connection, orders: dict[int, PreorderSummary]) -> None:
    if not orders:
        return
    rows = db.execute(text("""
        SELECT preorder_id, variant_id AS variantId, product_name_snapshot AS productName,
               sku_snapshot AS sku, unit_price AS unitPrice, quantity,
               allocated_quantity AS allocatedQuantity, line_total AS lineTotal
        FROM preorder_items WHERE preorder_id IN :orders ORDER BY preorder_id, preorder_item_id
    """).bindparams(bindparam("orders", expanding=True)), {"orders": list(orders)}).mappings()
    for row in rows:
        orders[row["preorder_id"]].items.append(PreorderLine.model_validate(row))


def list_preorders(db: Connection, actor: Actor, filters: PreorderFilters) -> list[PreorderSummary]:
    if filters.branchId is not None:
        require_branch_access(db, actor, filters.branchId)
        branches = [filters.branchId]
    else:
        branches = get_accessible_branch_ids(db, actor)
    if not branches:
        return []
    conditions = ["p.branch_id IN :branches"]
    params = {"store": actor.store_id, "branches": branches,
              "limit": filters.size, "offset": (filters.page - 1) * filters.size}
    for name, clause, value in (("status", "p.status=:status", filters.status),
                                ("payment", "p.payment_status=:payment", filters.paymentStatus)):
        if value is not None:
            conditions.append(clause)
            params[name] = value
    keyword = (filters.keyword or "").strip()
    if keyword:
        # A complete +84 phone number also finds its domestic snapshot representation.
        try:
            phone = normalize_phone(keyword)
        except ValueError:
            phone = keyword
        def pattern(value):
            return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        params.update(keyword=pattern(keyword), phone=pattern(phone))
        conditions.append("""(p.preorder_code LIKE :keyword ESCAPE '!' OR p.customer_name LIKE :keyword ESCAPE '!'
                               OR p.customer_phone LIKE :phone ESCAPE '!')""")
    rows = db.execute(text(HEADER_SELECT + " WHERE " + " AND ".join(conditions) +
                           " ORDER BY p.created_at ASC, p.preorder_id ASC LIMIT :limit OFFSET :offset"
                           ).bindparams(bindparam("branches", expanding=True)), params).mappings()
    orders = {row["preorderId"]: summary_from_row(row) for row in rows}
    load_items(db, orders)
    return list(orders.values())


def get_preorder_branch(db: Connection, actor: Actor, preorder_id: int, *, lock: bool = False) -> int:
    # A subquery scopes the order without locking its branch along with it.
    branch_id = db.execute(text("""
        SELECT p.branch_id FROM preorders AS p WHERE p.preorder_id=:id AND EXISTS (
            SELECT 1 FROM branches AS b WHERE b.branch_id=p.branch_id AND b.store_id=:store
        )
    """ + (" FOR UPDATE" if lock else "")), {"id": preorder_id, "store": actor.store_id}).scalar_one_or_none()
    if branch_id is None:
        raise HTTPException(404, {"code": "PREORDER_NOT_FOUND"})
    require_branch_access(db, actor, branch_id)
    return branch_id


def get_preorder(db: Connection, actor: Actor, preorder_id: int, *, lock: bool = False) -> PreorderDetail:
    get_preorder_branch(db, actor, preorder_id, lock=lock)
    header = db.execute(text(HEADER_SELECT + " WHERE p.preorder_id=:id"),
                        {"id": preorder_id, "store": actor.store_id}).mappings().one()
    summary = summary_from_row(header)
    load_items(db, {preorder_id: summary})
    payments = db.execute(text("""
        SELECT payment_id AS paymentId, payment_method AS paymentMethod, amount, status,
               confirmed_by AS confirmedBy, confirmed_at AS confirmedAt
        FROM payments WHERE preorder_id=:id ORDER BY payment_id
    """), {"id": preorder_id}).mappings()
    fulfillment = db.execute(text("""
        SELECT fulfillment_id AS fulfillmentId, fulfillment_method AS method, delivery_address AS deliveryAddress,
               status, confirmed_by AS confirmedBy, completed_at AS completedAt
        FROM preorder_fulfillments WHERE preorder_id=:id
    """), {"id": preorder_id}).mappings().one_or_none()
    notifications = db.execute(text("""
        SELECT notification_id AS notificationId, channel, recipient, message, status,
               provider_message_id AS providerMessageId, error_message AS errorMessage,
               sent_at AS sentAt, created_at AS createdAt
        FROM notifications WHERE preorder_id=:id ORDER BY created_at DESC, notification_id DESC
    """), {"id": preorder_id}).mappings()
    return PreorderDetail(
        **summary.model_dump(), payments=[OrderPayment.model_validate(row) for row in payments],
        fulfillment=PreorderFulfillment.model_validate(fulfillment) if fulfillment is not None else None,
        notifications=[PreorderNotification.model_validate(row) for row in notifications],
    )

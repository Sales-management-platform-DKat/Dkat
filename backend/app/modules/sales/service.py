from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor, get_accessible_branch_ids, require_branch_access
from app.modules.inventory.service import OPEN_PREORDER_STATUSES
from app.modules.sales.schemas import (
    OrderPayment, PendingSalesOrder, SalesOrderDetail, SalesOrderFilters,
    SalesOrderInput, SalesOrderLine, SalesOrderSummary,
)

MAX_ORDER_AMOUNT = Decimal("9999999999.99")
VIETNAM_TIME = timezone(timedelta(hours=7))
ORDER_SELECT = """
    SELECT o.sales_order_id AS salesOrderId, o.order_code AS orderCode,
           o.branch_id AS branchId, b.name AS branchName,
           o.customer_id AS customerId, c.full_name AS customerName,
           o.created_by AS createdBy, u.full_name AS createdByName,
           o.subtotal, o.discount_amount AS discountAmount, o.total_amount AS totalAmount,
           o.status, o.created_at AS createdAt, o.paid_at AS paidAt,
           o.cancelled_at AS cancelledAt, o.cancel_reason AS cancelReason
    FROM sales_orders AS o
    JOIN branches AS b ON b.branch_id = o.branch_id AND b.store_id = :store
    LEFT JOIN customers AS c ON c.customer_id = o.customer_id AND c.store_id = :store
    LEFT JOIN users AS u ON u.user_id = o.created_by AND u.store_id = :store
"""


def list_sales_orders(db: Connection, actor: Actor, filters: SalesOrderFilters) -> list[SalesOrderSummary]:
    if filters.branchId is not None:
        require_branch_access(db, actor, filters.branchId)
        branches = [filters.branchId]
    else:
        branches = get_accessible_branch_ids(db, actor)
    if not branches:
        return []
    conditions = ["o.branch_id IN :branches"]
    params = {
        "store": actor.store_id, "branches": branches, "limit": filters.size,
        "offset": (filters.page - 1) * filters.size,
    }
    end_operator = "<" if filters.end_exclusive else "<="
    for name, clause, value in (
        ("status", "o.status = :status", filters.status),
        ("customer", "o.customer_id = :customer", filters.customerId),
        ("start", "o.created_at >= :start", filters.utc_bound(filters.from_date)),
        ("end", f"o.created_at {end_operator} :end", filters.utc_bound(filters.to_date, end=True)),
    ):
        if value is not None:
            conditions.append(clause)
            params[name] = value
    keyword = (filters.keyword or "").strip()
    if keyword:
        conditions.append("(o.order_code LIKE :keyword ESCAPE '!' OR c.full_name LIKE :keyword ESCAPE '!')")
        params["keyword"] = "%" + keyword.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    rows = db.execute(
        text(ORDER_SELECT + " WHERE " + " AND ".join(conditions) +
             " ORDER BY o.created_at DESC, o.sales_order_id DESC LIMIT :limit OFFSET :offset"
        ).bindparams(bindparam("branches", expanding=True)),
        params,
    ).mappings()
    orders = {row["salesOrderId"]: SalesOrderSummary.model_validate(row) for row in rows}
    if orders:
        methods = db.execute(
            text("""
                SELECT DISTINCT sales_order_id, payment_method FROM payments
                WHERE sales_order_id IN :orders AND status = 'SUCCESS'
                ORDER BY sales_order_id, payment_method
            """).bindparams(bindparam("orders", expanding=True)),
            {"orders": list(orders)},
        )
        for order_id, method in methods:
            orders[order_id].paymentMethods.append(method)
    return list(orders.values())


def get_sales_order(
    db: Connection, actor: Actor, order_id: int, *, lock: bool = False,
) -> SalesOrderDetail:
    header = db.execute(
        text("""
            SELECT o.branch_id FROM sales_orders AS o
            JOIN branches AS b ON b.branch_id = o.branch_id AND b.store_id = :store
            WHERE o.sales_order_id = :id
        """ + (" FOR UPDATE" if lock else "")),
        {"store": actor.store_id, "id": order_id},
    ).scalar_one_or_none()
    if header is None:
        raise HTTPException(404, {"code": "ORDER_NOT_FOUND"})
    require_branch_access(db, actor, header)
    row = db.execute(
        text(ORDER_SELECT + " WHERE o.sales_order_id = :id"),
        {"store": actor.store_id, "id": order_id},
    ).mappings().one()
    lines = db.execute(
        text("""
            SELECT variant_id AS variantId, product_name_snapshot AS productName,
                   sku_snapshot AS sku, unit_price AS unitPrice, quantity, line_total AS lineTotal
            FROM sales_order_items WHERE sales_order_id = :id ORDER BY sales_order_item_id
        """),
        {"id": order_id},
    ).mappings()
    payments = db.execute(
        text("""
            SELECT payment_id AS paymentId, payment_method AS paymentMethod, amount, status,
                   confirmed_by AS confirmedBy, confirmed_at AS confirmedAt
            FROM payments WHERE sales_order_id = :id ORDER BY payment_id
        """),
        {"id": order_id},
    ).mappings()
    payment_records = [OrderPayment.model_validate(payment) for payment in payments]
    return SalesOrderDetail(
        **row, items=[SalesOrderLine.model_validate(line) for line in lines],
        payments=payment_records,
        paymentMethods=sorted({payment.paymentMethod for payment in payment_records if payment.status == "SUCCESS"}),
    )


def cancel_sales_order(db: Connection, actor: Actor, order_id: int, reason: str) -> SalesOrderDetail:
    order = get_sales_order(db, actor, order_id, lock=True)
    if order.status != "PENDING":
        raise HTTPException(409, {"code": "ORDER_NOT_PENDING"})
    db.execute(
        text("""
            UPDATE sales_orders SET status = 'CANCELLED', cancel_reason = :reason,
                                    cancelled_at = UTC_TIMESTAMP()
            WHERE sales_order_id = :id AND status = 'PENDING'
        """),
        {"id": order_id, "reason": reason},
    )
    return get_sales_order(db, actor, order_id)


def price_order(db: Connection, store_id: int, order: SalesOrderInput) -> list[SalesOrderLine]:
    variant_ids = [item.variantId for item in order.items]
    rows = db.execute(
        text(f"""
            SELECT v.variant_id, v.sku, v.price, v.status AS variant_status,
                   p.name, p.status AS product_status,
                   CAST(COALESCE(i.quantity, 0) AS SIGNED) - COALESCE(reservations.reserved, 0) AS available
            FROM product_variants AS v
            JOIN products AS p ON p.product_id = v.product_id AND p.store_id = :store
            LEFT JOIN inventory AS i ON i.variant_id = v.variant_id AND i.branch_id = :branch
            LEFT JOIN (
                SELECT item.variant_id, SUM(item.allocated_quantity) AS reserved
                FROM preorders AS po
                JOIN preorder_items AS item ON item.preorder_id = po.preorder_id
                WHERE po.branch_id = :branch AND po.status IN ({OPEN_PREORDER_STATUSES})
                  AND item.variant_id IN :variants
                GROUP BY item.variant_id
            ) AS reservations ON reservations.variant_id = v.variant_id
            WHERE v.variant_id IN :variants
        """).bindparams(bindparam("variants", expanding=True)),
        {"store": store_id, "branch": order.branchId, "variants": variant_ids},
    ).mappings()
    variants = {row["variant_id"]: row for row in rows}
    missing = [variant_id for variant_id in variant_ids if variant_id not in variants]
    if missing:
        raise HTTPException(404, {"code": "VARIANT_NOT_FOUND", "variantIds": missing})

    inactive = [
        variant_id for variant_id, row in variants.items()
        if row["variant_status"] != "ACTIVE" or row["product_status"] != "ACTIVE"
    ]
    if inactive:
        raise HTTPException(409, {"code": "VARIANT_INACTIVE", "variantIds": sorted(inactive)})

    shortages = []
    lines = []
    for item in order.items:
        variant = variants[item.variantId]
        available = int(variant["available"])
        if item.quantity > available:
            shortages.append({"variantId": item.variantId, "available": available})
            continue
        price = variant["price"]
        lines.append(SalesOrderLine(
            variantId=item.variantId, productName=variant["name"], sku=variant["sku"],
            unitPrice=price, quantity=item.quantity, lineTotal=price * item.quantity,
        ))
    if shortages:
        raise HTTPException(409, {"code": "OUT_OF_STOCK", "items": shortages})
    return lines


def create_sales_order(db: Connection, actor: Actor, order: SalesOrderInput) -> PendingSalesOrder:
    require_branch_access(db, actor, order.branchId)
    if order.customerId is not None:
        customer = db.execute(
            text("SELECT customer_id FROM customers WHERE store_id = :store AND customer_id = :id"),
            {"store": actor.store_id, "id": order.customerId},
        ).scalar_one_or_none()
        if customer is None:
            raise HTTPException(404, {"code": "CUSTOMER_NOT_FOUND"})

    # Stock is checked here and checked again under lock when payment is confirmed.
    lines = price_order(db, actor.store_id, order)
    subtotal = sum((line.lineTotal for line in lines), Decimal("0.00"))
    discount = order.discountAmount.quantize(Decimal("0.01"))
    if subtotal > MAX_ORDER_AMOUNT:
        raise HTTPException(422, {"code": "ORDER_AMOUNT_TOO_LARGE"})
    if discount > subtotal:
        raise HTTPException(422, {"code": "DISCOUNT_EXCEEDS_SUBTOTAL"})

    total = subtotal - discount
    order_code = f"DK-{datetime.now(VIETNAM_TIME):%y%m%d}-{uuid4().hex.upper()}"
    order_id = db.execute(
        text("""
            INSERT INTO sales_orders
                (order_code, branch_id, customer_id, created_by, subtotal, discount_amount, total_amount, status)
            VALUES (:code, :branch, :customer, :user, :subtotal, :discount, :total, 'PENDING')
        """),
        {
            "code": order_code, "branch": order.branchId, "customer": order.customerId,
            "user": actor.user_id, "subtotal": subtotal, "discount": discount, "total": total,
        },
    ).lastrowid
    db.execute(
        text("""
            INSERT INTO sales_order_items
                (sales_order_id, variant_id, product_name_snapshot, sku_snapshot, unit_price, quantity, line_total)
            VALUES (:order, :variantId, :productName, :sku, :unitPrice, :quantity, :lineTotal)
        """),
        [{"order": order_id, **line.model_dump()} for line in lines],
    )
    return PendingSalesOrder(
        salesOrderId=order_id, orderCode=order_code, branchId=order.branchId, customerId=order.customerId,
        subtotal=subtotal, discountAmount=discount, totalAmount=total, items=lines,
    )

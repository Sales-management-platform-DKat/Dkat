from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.core.permissions import Actor, require_branch_access
from app.modules.inventory.service import OPEN_PREORDER_STATUSES
from app.modules.sales.schemas import PendingSalesOrder, SalesOrderInput, SalesOrderLine

MAX_ORDER_AMOUNT = Decimal("9999999999.99")
VIETNAM_TIME = timezone(timedelta(hours=7))


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

from decimal import Decimal
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import bindparam, text

from app.core.exceptions import AppError
from app.core.permissions import Actor, get_accessible_branch_ids, require_auth
from app.db.session import engine
from app.modules.sales.schemas import ConfirmPaymentInput, RefundInput, SalesOrderCreate, SalesOrderRecord

router = APIRouter(prefix="/sales-orders", tags=["sales"])
Reader = Annotated[Actor, Depends(require_auth)]


@router.post("", status_code=201, response_model=SalesOrderRecord)
def create_sales_order(data: SalesOrderCreate, actor: Reader) -> SalesOrderRecord:
    variant_ids = [line.variantId for line in data.items]
    if len(variant_ids) != len(set(variant_ids)):
        raise AppError.validation("A variant can appear only once in an order.")

    with engine.execution_options(isolation_level='READ COMMITTED').begin() as db:
        if not get_accessible_branch_ids(db, actor, data.branchId):
            raise AppError.forbidden("Branch is not assigned to this account.")
        branch = db.execute(text("SELECT status FROM branches WHERE branch_id=:branch AND store_id=:store FOR UPDATE"), {"branch": data.branchId, "store": actor.store_id}).scalar_one_or_none()
        if branch != "ACTIVE":
            raise AppError.conflict("Branch is not active.")
        customer = None
        if data.customerId is not None:
            customer = db.execute(text("SELECT customer_id, full_name FROM customers WHERE customer_id=:id AND store_id=:store"), {"id":data.customerId,"store":actor.store_id}).mappings().one_or_none()
            if customer is None: raise AppError.validation("Customer is not part of this store.", [{"field":"customerId","message":"Choose a valid customer."}])

        rows = db.execute(
            text("""
                SELECT v.variant_id, v.sku, v.variant_name, v.price, p.name AS product_name,
                       i.inventory_id, i.quantity,
                       COALESCE((SELECT SUM(pi.allocated_quantity)
                         FROM preorder_items pi JOIN preorders po ON po.preorder_id=pi.preorder_id
                         WHERE pi.variant_id=v.variant_id AND po.branch_id=:branch
                           AND po.status IN ('WAITING_STOCK','READY','NOTIFIED')), 0) +
                       COALESCE((SELECT SUM(oi.quantity)
                         FROM sales_order_items oi JOIN sales_orders so ON so.sales_order_id=oi.sales_order_id
                         WHERE oi.variant_id=v.variant_id AND so.branch_id=:branch AND so.status='PENDING'), 0) AS reserved
                FROM product_variants v
                JOIN products p ON p.product_id=v.product_id AND p.store_id=:store
                LEFT JOIN inventory i ON i.variant_id=v.variant_id AND i.branch_id=:branch
                WHERE v.variant_id IN :variants AND v.status='ACTIVE'
                FOR UPDATE
            """).bindparams(bindparam("variants", expanding=True)),
            {"store": actor.store_id, "branch": data.branchId, "variants": variant_ids},
        ).mappings().all()
        by_id = {row["variant_id"]: row for row in rows}
        if len(by_id) != len(variant_ids):
            raise AppError.validation("One or more variants are unavailable.", [{"field": "items", "message": "Choose active variants from this store."}])

        subtotal = Decimal("0.00")
        items = []
        for line in data.items:
            row = by_id[line.variantId]
            available = (row["quantity"] or 0) - (row["reserved"] or 0)
            if line.quantity > available:
                raise AppError(409, "OUT_OF_STOCK", f"Insufficient stock for SKU {row['sku']}.", {"variantId": line.variantId, "available": max(0, available)})
            unit_price = Decimal(row["price"])
            line_total = unit_price * line.quantity
            subtotal += line_total
            items.append({"variantId": line.variantId, "productName": row["product_name"], "sku": row["sku"], "unitPrice": unit_price, "quantity": line.quantity, "lineTotal": line_total})

        if data.discountAmount > subtotal:
            raise AppError.validation("Discount cannot exceed the subtotal.", [{"field": "discountAmount", "message": "Must not exceed subtotal."}])
        total = subtotal - data.discountAmount
        order_code = "SO-" + uuid4().hex[:16].upper()
        order_id = db.execute(text("""
            INSERT INTO sales_orders (order_code, branch_id, customer_id, created_by, subtotal, discount_amount, total_amount, status)
            VALUES (:code, :branch, :customer, :user, :subtotal, :discount, :total, 'PENDING')
        """), {"code": order_code, "branch": data.branchId, "customer":data.customerId, "user": actor.user_id, "subtotal": subtotal, "discount": data.discountAmount, "total": total}).lastrowid
        for item in items:
            db.execute(text("""
                INSERT INTO sales_order_items (sales_order_id, variant_id, product_name_snapshot, sku_snapshot, unit_price, quantity, line_total)
                VALUES (:order, :variant, :name, :sku, :price, :quantity, :total)
            """), {"order": order_id, "variant": item["variantId"], "name": item["productName"], "sku": item["sku"], "price": item["unitPrice"], "quantity": item["quantity"], "total": item["lineTotal"]})

    return SalesOrderRecord(salesOrderId=order_id, orderCode=order_code, branchId=data.branchId, customerId=data.customerId, customerName=customer["full_name"] if customer else "Guest", subtotal=subtotal, discountAmount=data.discountAmount, totalAmount=total, status="PENDING", items=items)


def _order_items(db, order_id: int):
    return [dict(row) for row in db.execute(text("""
        SELECT variant_id AS variantId, product_name_snapshot AS productName,
               sku_snapshot AS sku, unit_price AS unitPrice, quantity, line_total AS lineTotal
        FROM sales_order_items WHERE sales_order_id=:order ORDER BY sales_order_item_id
    """), {"order": order_id}).mappings()]


def _order_detail(db, actor: Actor, order_id: int):
    row = db.execute(text("""
        SELECT so.sales_order_id AS salesOrderId, so.order_code AS orderCode,
               so.branch_id AS branchId, b.name AS branchName, so.created_by AS createdBy,
               u.full_name AS employeeName, c.full_name AS customerName, so.customer_id AS customerId, so.subtotal, so.discount_amount AS discountAmount,
               so.total_amount AS totalAmount, so.status, so.created_at AS createdAt, so.paid_at AS paidAt
        FROM sales_orders so JOIN branches b ON b.branch_id=so.branch_id LEFT JOIN customers c ON c.customer_id=so.customer_id
        JOIN users u ON u.user_id=so.created_by
        WHERE so.sales_order_id=:id AND b.store_id=:store
    """), {"id": order_id, "store": actor.store_id}).mappings().one_or_none()
    if row is None:
        raise AppError.not_found("Sales order not found.")
    if not get_accessible_branch_ids(db, actor, row["branchId"]):
        raise AppError.forbidden("Branch is not assigned to this account.")
    result = dict(row)
    result["customerName"] = result.get("customerName") or "Guest"
    result["items"] = _order_items(db, order_id)
    result["payments"] = [dict(payment) for payment in db.execute(text("""
        SELECT payment_id AS paymentId, payment_method AS paymentMethod, amount, status,
               confirmed_by AS confirmedBy, confirmed_at AS confirmedAt
        FROM payments WHERE sales_order_id=:id ORDER BY payment_id
    """), {"id": order_id}).mappings()]
    return result


@router.get("")
def list_sales_orders(
    actor: Reader,
    status: str | None = None,
    branch_id: int | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    size: int = 50,
):
    if page < 1 or size < 1 or size > 100:
        raise AppError.validation("Invalid pagination.")
    with engine.connect() as db:
        branch_ids = get_accessible_branch_ids(db, actor, branch_id)
        if not branch_ids:
            return []
        sql = text("""
            SELECT so.sales_order_id AS salesOrderId, so.order_code AS orderCode,
                   so.branch_id AS branchId, b.name AS branchName, so.created_by AS createdBy,
                   u.full_name AS employeeName, c.full_name AS customerName, so.customer_id AS customerId, so.subtotal, so.discount_amount AS discountAmount,
                   so.total_amount AS totalAmount, so.status, so.created_at AS createdAt, so.paid_at AS paidAt
            FROM sales_orders so JOIN branches b ON b.branch_id=so.branch_id LEFT JOIN customers c ON c.customer_id=so.customer_id
            JOIN users u ON u.user_id=so.created_by
            WHERE b.store_id=:store AND b.branch_id IN :branches
              AND (:status IS NULL OR so.status=:status)
              AND (:keyword IS NULL OR so.order_code LIKE :keyword)
              AND (:date_from IS NULL OR so.created_at >= :date_from)
              AND (:date_to IS NULL OR so.created_at < DATE_ADD(:date_to, INTERVAL 1 DAY))
            ORDER BY so.created_at DESC, so.sales_order_id DESC LIMIT :limit OFFSET :offset
        """).bindparams(bindparam("branches", expanding=True))
        rows = db.execute(sql, {"store": actor.store_id, "branches": branch_ids, "status": status,
            "keyword": f"%{keyword.strip()}%" if keyword and keyword.strip() else None,
            "date_from": date_from, "date_to": date_to, "limit": size, "offset": (page-1)*size}).mappings()
        result=[]
        for row in rows:
            item=dict(row); item["customerName"]=item.get("customerName") or "Guest"; item["items"]=_order_items(db,item["salesOrderId"])
            item["payments"]=[dict(p) for p in db.execute(text("SELECT payment_method AS paymentMethod, amount, status, confirmed_at AS confirmedAt FROM payments WHERE sales_order_id=:id ORDER BY payment_id"),{"id":item["salesOrderId"]}).mappings()]
            result.append(item)
        return result


@router.get("/{order_id}")
def get_sales_order(order_id: int, actor: Reader):
    with engine.connect() as db:
        return _order_detail(db, actor, order_id)


@router.post("/{order_id}/confirm-payment")
def confirm_sales_order_payment(order_id: int, data: ConfirmPaymentInput, actor: Reader):
    with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
        order = db.execute(text("SELECT so.branch_id, so.status, so.total_amount FROM sales_orders so JOIN branches b ON b.branch_id=so.branch_id WHERE so.sales_order_id=:id AND b.store_id=:store FOR UPDATE"), {"id":order_id,"store":actor.store_id}).mappings().one_or_none()
        if order is None: raise AppError.not_found("Sales order not found.")
        if not get_accessible_branch_ids(db,actor,order["branch_id"]): raise AppError.forbidden("Branch is not assigned to this account.")
        if order["status"] != "PENDING": raise AppError.conflict("Only pending orders can be paid.")
        total=Decimal(order["total_amount"])
        if data.paymentMethod == "CASH" and (data.amountTendered is None or data.amountTendered < total):
            raise AppError.validation("Cash received must cover the order total.", [{"field":"amountTendered","message":"Must be at least the order total."}])
        lines=db.execute(text("SELECT variant_id, quantity FROM sales_order_items WHERE sales_order_id=:id ORDER BY variant_id"),{"id":order_id}).all()
        for variant_id, quantity in lines:
            stock=db.execute(text("SELECT i.inventory_id, i.quantity FROM inventory i WHERE i.branch_id=:branch AND i.variant_id=:variant FOR UPDATE"),{"branch":order["branch_id"],"variant":variant_id}).one_or_none()
            if stock is None or stock.quantity < quantity:
                raise AppError.conflict("Stock changed before payment could be confirmed.", {"code":"OUT_OF_STOCK","variantId":variant_id,"available":stock.quantity if stock else 0})
        for variant_id, quantity in lines:
            stock=db.execute(text("SELECT inventory_id, quantity FROM inventory WHERE branch_id=:branch AND variant_id=:variant"),{"branch":order["branch_id"],"variant":variant_id}).one()
            db.execute(text("UPDATE inventory SET quantity=:quantity WHERE inventory_id=:id"),{"quantity":stock.quantity-quantity,"id":stock.inventory_id})
            db.execute(text("INSERT INTO inventory_movements (inventory_id,movement_type,quantity_change,reference_type,reference_id,note,created_by) VALUES (:inventory,'SALE',:delta,'SALES_ORDER',:order,'POS sale',:user)"),{"inventory":stock.inventory_id,"delta":-quantity,"order":order_id,"user":actor.user_id})
        db.execute(text("INSERT INTO payments (sales_order_id,payment_method,amount,status,confirmed_by,confirmed_at) VALUES (:order,:method,:amount,'SUCCESS',:user,NOW())"),{"order":order_id,"method":data.paymentMethod,"amount":total,"user":actor.user_id})
        db.execute(text("UPDATE sales_orders SET status='PAID', paid_at=NOW() WHERE sales_order_id=:id"),{"id":order_id})
    with engine.connect() as db: return _order_detail(db,actor,order_id)


@router.post("/{order_id}/cancel")
def cancel_sales_order(order_id: int, actor: Reader):
    with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
        order=db.execute(text("SELECT so.branch_id,so.status FROM sales_orders so JOIN branches b ON b.branch_id=so.branch_id WHERE so.sales_order_id=:id AND b.store_id=:store FOR UPDATE"),{"id":order_id,"store":actor.store_id}).mappings().one_or_none()
        if order is None: raise AppError.not_found("Sales order not found.")
        if not get_accessible_branch_ids(db,actor,order["branch_id"]): raise AppError.forbidden("Branch is not assigned to this account.")
        if order["status"] != "PENDING": raise AppError.conflict("Only pending orders can be cancelled.")
        db.execute(text("UPDATE sales_orders SET status='CANCELLED' WHERE sales_order_id=:id"),{"id":order_id})
    with engine.connect() as db: return _order_detail(db,actor,order_id)


@router.post("/{order_id}/refund")
def refund_sales_order(order_id: int, data: RefundInput, actor: Reader):
    if actor.role not in {"OWNER", "MANAGER"}: raise AppError.forbidden("Only OWNER or MANAGER can refund a paid order.")
    with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
        order=db.execute(text("SELECT so.branch_id,so.status FROM sales_orders so JOIN branches b ON b.branch_id=so.branch_id WHERE so.sales_order_id=:id AND b.store_id=:store FOR UPDATE"),{"id":order_id,"store":actor.store_id}).mappings().one_or_none()
        if order is None: raise AppError.not_found("Sales order not found.")
        if not get_accessible_branch_ids(db,actor,order["branch_id"]): raise AppError.forbidden("Branch is not assigned to this account.")
        if order["status"] != "PAID": raise AppError.conflict("Only paid orders can be refunded.")
        lines=db.execute(text("SELECT variant_id,quantity FROM sales_order_items WHERE sales_order_id=:id ORDER BY variant_id"),{"id":order_id}).all()
        for variant_id, quantity in lines:
            stock=db.execute(text("SELECT inventory_id,quantity FROM inventory WHERE branch_id=:branch AND variant_id=:variant FOR UPDATE"),{"branch":order["branch_id"],"variant":variant_id}).one_or_none()
            if stock is None: raise AppError.conflict("Inventory row is missing; refund cannot restore stock.")
            db.execute(text("UPDATE inventory SET quantity=:quantity WHERE inventory_id=:id"),{"quantity":stock.quantity+quantity,"id":stock.inventory_id})
            db.execute(text("INSERT INTO inventory_movements (inventory_id,movement_type,quantity_change,reference_type,reference_id,note,created_by) VALUES (:inventory,'ADJUSTMENT',:delta,'SALES_ORDER',:order,:note,:user)"),{"inventory":stock.inventory_id,"delta":quantity,"order":order_id,"note":"Refund: "+data.reason,"user":actor.user_id})
        db.execute(text("UPDATE payments SET status='REFUNDED' WHERE sales_order_id=:id AND status='SUCCESS'"),{"id":order_id})
        db.execute(text("UPDATE sales_orders SET status='CANCELLED' WHERE sales_order_id=:id"),{"id":order_id})
    with engine.connect() as db: return _order_detail(db,actor,order_id)

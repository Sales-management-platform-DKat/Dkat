from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.modules.customers.service import upsert_customer_by_phone
from app.modules.inventory.service import lock_inventory_rows, reserved_quantities
from app.modules.preorders.errors import PreorderError
from app.modules.preorders.schemas import CreatedPreorder, PreorderInput, PreorderLine

MAX_AMOUNT = Decimal("9999999999.99")
VIETNAM_TIME = timezone(timedelta(hours=7))


def create_preorder(db: Connection, data: PreorderInput) -> CreatedPreorder:
    branch = db.execute(
        text("SELECT store_id FROM branches WHERE branch_id=:id AND status='ACTIVE'"),
        {"id": data.branchId},
    ).scalar_one_or_none()
    if branch is None:
        raise PreorderError(404, "BRANCH_NOT_FOUND", "Không tìm thấy chi nhánh đang hoạt động")
    variant_ids = sorted(item.variantId for item in data.items)
    variants = {row["variant_id"]: row for row in db.execute(
        text("""
            SELECT v.variant_id, v.sku, v.price, v.status AS variant_status,
                   p.name, p.status AS product_status
            FROM product_variants AS v
            JOIN products AS p ON p.product_id=v.product_id AND p.store_id=:store
            WHERE v.variant_id IN :variants
        """).bindparams(bindparam("variants", expanding=True)),
        {"store": branch, "variants": variant_ids},
    ).mappings()}
    if any(variant not in variants for variant in variant_ids):
        raise PreorderError(404, "VARIANT_NOT_FOUND", "Không tìm thấy biến thể trong cửa hàng")
    if any(row["variant_status"] != "ACTIVE" or row["product_status"] != "ACTIVE" for row in variants.values()):
        raise PreorderError(409, "VARIANT_INACTIVE", "Sản phẩm hoặc biến thể đã ngừng hoạt động")

    inventory = lock_inventory_rows(db, data.branchId, variant_ids, create_missing=False)
    reserved = reserved_quantities(db, data.branchId, variant_ids)
    in_stock = []
    lines = []
    for index, item in enumerate(data.items):
        available = inventory.get(item.variantId, (None, 0))[1] - reserved.get(item.variantId, 0)
        if available >= item.quantity:
            in_stock.append({"field": f"items.{index}.quantity",
                             "reason": f"Biến thể {item.variantId} còn đủ {available} hàng khả dụng"})
        variant = variants[item.variantId]
        lines.append(PreorderLine(
            variantId=item.variantId, productName=variant["name"], sku=variant["sku"],
            unitPrice=variant["price"], quantity=item.quantity, lineTotal=variant["price"] * item.quantity,
        ))
    if in_stock:
        raise PreorderError(409, "VARIANT_IN_STOCK", "Hàng còn đủ; vui lòng mua trực tiếp tại cửa hàng", in_stock)
    total = sum((line.lineTotal for line in lines), Decimal("0.00"))
    if total > MAX_AMOUNT:
        raise PreorderError(422, "INVALID_PREORDER", "Đơn đặt trước không hợp lệ",
                            [{"field": "items", "reason": "Tổng tiền vượt giới hạn cho phép"}])
    customer_id = upsert_customer_by_phone(
        db, store_id=branch, full_name=data.customer.fullName, phone=data.customer.phone,
        email=data.customer.email, address=data.customer.address,
    )
    now = datetime.now(timezone.utc)
    code = f"PD-{now.astimezone(VIETNAM_TIME):%y%m%d}-{uuid4().hex.upper()}"
    preorder_id = db.execute(
        text("""
            INSERT INTO preorders
                (preorder_code, branch_id, customer_id, customer_name, customer_phone, customer_email,
                 customer_address, note, total_amount, payment_status, status, created_at)
            VALUES (:code, :branch, :customer, :name, :phone, :email, :address, :note, :total,
                    'UNPAID', 'WAITING_STOCK', :at)
        """),
        {
            "code": code, "branch": data.branchId, "customer": customer_id,
            "name": data.customer.fullName, "phone": data.customer.phone, "email": data.customer.email,
            "address": data.customer.address, "note": data.note, "total": total,
            "at": now.replace(tzinfo=None),
        },
    ).lastrowid
    db.execute(
        text("""
            INSERT INTO preorder_items
                (preorder_id, variant_id, product_name_snapshot, sku_snapshot, unit_price,
                 quantity, allocated_quantity, line_total)
            VALUES (:order, :variantId, :productName, :sku, :unitPrice, :quantity, 0, :lineTotal)
        """),
        [{"order": preorder_id, **line.model_dump()} for line in lines],
    )
    return CreatedPreorder(
        preorderId=preorder_id, preorderCode=code, branchId=data.branchId, customerId=customer_id,
        customer=data.customer, totalAmount=total, note=data.note, items=lines, createdAt=now,
    )

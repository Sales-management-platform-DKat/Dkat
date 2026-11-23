"""SQL for a customer's purchase history: POS sales orders + pre-orders linked to the customer.

Tables are owned by the sales / pre-order modules; this file only reads them.
- sales_orders.customer_id (database/04_sales_order_customers.sql), preorders.customer_id (06_public_preorders.sql)
- Index use: fk_sales_orders_customer_id / fk_preorders_customer_id (customer_id), branches PRIMARY,
  payments idx_pay_sales_order / idx_pay_preorder, order items idx_soi_order_variant / idx_pi_preorder.
Walk-in orders have customer_id NULL and never appear here.
"""
from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

# A completed purchase (counted in the statistics)
COMPLETED_SALE_STATUS = "PAID"
COMPLETED_PREORDER_STATUS = "FULFILLED"


def _filters(alias: str, branch_ids: list[int] | None, date_from: datetime | None, date_to: datetime | None) -> str:
    sql = f" AND {alias}.customer_id = :customer_id"
    if branch_ids is not None:
        sql += f" AND {alias}.branch_id IN :branch_ids"
    if date_from is not None:
        sql += f" AND {alias}.created_at >= :date_from"
    if date_to is not None:
        sql += f" AND {alias}.created_at < :date_to"  # exclusive: caller passes the day after `to`
    return sql


def _union_sql(branch_ids, date_from, date_to, *, completed_only: bool = False) -> str:
    sale_status = f" AND so.status = '{COMPLETED_SALE_STATUS}'" if completed_only else ""
    pre_status = f" AND po.status = '{COMPLETED_PREORDER_STATUS}'" if completed_only else ""
    return f"""
        SELECT 'SALE' AS type, so.sales_order_id AS id, so.order_code AS code, so.created_at,
               so.branch_id, b.name AS branch_name, so.total_amount, so.status, NULL AS payment_status,
               (SELECT GROUP_CONCAT(DISTINCT p.payment_method ORDER BY p.payment_method)
                  FROM payments p WHERE p.sales_order_id = so.sales_order_id AND p.status = 'SUCCESS') AS methods
        FROM sales_orders so JOIN branches b ON b.branch_id = so.branch_id
        WHERE 1 = 1 {_filters("so", branch_ids, date_from, date_to)}{sale_status}
        UNION ALL
        SELECT 'PREORDER', po.preorder_id, po.preorder_code, po.created_at,
               po.branch_id, b.name, po.total_amount, po.status, po.payment_status,
               (SELECT GROUP_CONCAT(DISTINCT p.payment_method ORDER BY p.payment_method)
                  FROM payments p WHERE p.preorder_id = po.preorder_id AND p.status = 'SUCCESS')
        FROM preorders po JOIN branches b ON b.branch_id = po.branch_id
        WHERE 1 = 1 {_filters("po", branch_ids, date_from, date_to)}{pre_status}
    """


def _params(customer_id, branch_ids, date_from, date_to) -> dict:
    params = {"customer_id": customer_id, "date_from": date_from, "date_to": date_to}
    if branch_ids is not None:
        params["branch_ids"] = branch_ids
    return params


def _text(sql: str, branch_ids):
    stmt = text(sql)
    return stmt.bindparams(bindparam("branch_ids", expanding=True)) if branch_ids is not None else stmt


async def list_orders(
    db: AsyncSession,
    customer_id: int,
    *,
    branch_ids: list[int] | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    size: int,
) -> tuple[list, int, int, float]:
    """(rows of one page, total rows, completed purchase count, completed total spent).

    branch_ids=None -> every branch (OWNER); a list -> only those branches (empty list -> nothing).
    """
    if branch_ids is not None and not branch_ids:
        return [], 0, 0, 0.0
    params = _params(customer_id, branch_ids, date_from, date_to)
    union = _union_sql(branch_ids, date_from, date_to)

    total = (await db.execute(_text(f"SELECT COUNT(*) FROM ({union}) o", branch_ids), params)).scalar_one()
    rows = (
        await db.execute(
            _text(f"SELECT * FROM ({union}) o ORDER BY o.created_at DESC, o.type, o.id DESC LIMIT :limit OFFSET :offset", branch_ids),
            {**params, "limit": size, "offset": (page - 1) * size},
        )
    ).mappings().all()
    completed = _union_sql(branch_ids, date_from, date_to, completed_only=True)
    count, spent = (
        await db.execute(_text(f"SELECT COUNT(*), COALESCE(SUM(o.total_amount), 0) FROM ({completed}) o", branch_ids), params)
    ).one()
    return list(rows), int(total), int(count), float(spent)


async def get_order(db: AsyncSession, customer_id: int, order_type: str, order_id: int):
    """Header row of one order of this customer (any branch), or None."""
    union = _union_sql(None, None, None)
    return (
        await db.execute(
            text(f"SELECT * FROM ({union}) o WHERE o.type = :type AND o.id = :id"),
            {"customer_id": customer_id, "date_from": None, "date_to": None, "type": order_type, "id": order_id},
        )
    ).mappings().first()


async def sale_amounts(db: AsyncSession, sales_order_id: int):
    return (
        await db.execute(
            text("SELECT subtotal, discount_amount FROM sales_orders WHERE sales_order_id = :id"), {"id": sales_order_id}
        )
    ).one()


async def order_lines(db: AsyncSession, order_type: str, order_id: int) -> list:
    if order_type == "SALE":
        sql = """SELECT product_name_snapshot AS product_name, sku_snapshot AS sku, unit_price, quantity, line_total
                 FROM sales_order_items WHERE sales_order_id = :id ORDER BY sales_order_item_id"""
    else:
        sql = """SELECT product_name_snapshot AS product_name, sku_snapshot AS sku, unit_price, quantity, line_total
                 FROM preorder_items WHERE preorder_id = :id ORDER BY preorder_item_id"""
    return list((await db.execute(text(sql), {"id": order_id})).mappings().all())


async def order_payments(db: AsyncSession, order_type: str, order_id: int) -> list:
    column = "sales_order_id" if order_type == "SALE" else "preorder_id"
    sql = f"""SELECT payment_method AS method, amount, status, confirmed_at
              FROM payments WHERE {column} = :id ORDER BY payment_id"""
    return list((await db.execute(text(sql), {"id": order_id})).mappings().all())

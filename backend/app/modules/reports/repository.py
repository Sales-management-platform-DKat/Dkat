"""SQL for revenue reports. Read-only; tables belong to the sales / pre-order modules.

Revenue (FR-06):
- POS sales orders with status PAID, dated by paid_at;
- pre-orders with status FULFILLED and payment not REFUNDED, dated by fulfilled_at.
CANCELLED sales orders (including refunded ones: the refund sets CANCELLED) never count.

paid_at / fulfilled_at are stored in UTC (written with UTC_TIMESTAMP() / datetime.now(timezone.utc)).
Days are computed in Vietnam time with a fixed +7h offset (Vietnam has no daylight saving time, and
the MySQL time-zone tables are not required).
"""
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

VN_OFFSET_HOURS = 7


async def daily_revenue(
    db: AsyncSession, store_id: int, *, start_utc: datetime, end_utc: datetime, branch_id: int | None
) -> dict[date, dict]:
    """{Vietnam date: {sales, sales_count, preorders, preorder_count}} for days that have revenue."""
    branch_sql = " AND o.branch_id = :branch_id" if branch_id is not None else ""
    params = {"store_id": store_id, "start": start_utc, "end": end_utc, "branch_id": branch_id}
    result: dict[date, dict] = {}

    for kind, sql in (
        (
            "sales",
            f"""SELECT DATE(DATE_ADD(o.paid_at, INTERVAL {VN_OFFSET_HOURS} HOUR)) AS d,
                       COUNT(*) AS n, SUM(o.total_amount) AS amount
                FROM sales_orders o JOIN branches b ON b.branch_id = o.branch_id AND b.store_id = :store_id
                WHERE o.status = 'PAID' AND o.paid_at >= :start AND o.paid_at < :end{branch_sql}
                GROUP BY d""",
        ),
        (
            "preorders",
            f"""SELECT DATE(DATE_ADD(o.fulfilled_at, INTERVAL {VN_OFFSET_HOURS} HOUR)) AS d,
                       COUNT(*) AS n, SUM(o.total_amount) AS amount
                FROM preorders o JOIN branches b ON b.branch_id = o.branch_id AND b.store_id = :store_id
                WHERE o.status = 'FULFILLED' AND o.payment_status <> 'REFUNDED'
                  AND o.fulfilled_at >= :start AND o.fulfilled_at < :end{branch_sql}
                GROUP BY d""",
        ),
    ):
        for row in (await db.execute(text(sql), params)).mappings():
            day = result.setdefault(row["d"], {"sales": 0.0, "sales_count": 0, "preorders": 0.0, "preorder_count": 0})
            day[kind] = float(row["amount"])
            day["sales_count" if kind == "sales" else "preorder_count"] = int(row["n"])
    return result


async def product_lines(
    db: AsyncSession, store_id: int, *, start_utc: datetime, end_utc: datetime, branch_id: int | None
) -> list:
    """Snapshot lines of the orders that count as revenue (same rule as daily_revenue), grouped by
    (SKU, product name snapshot): sku, name, quantity, revenue (sum of line_total), last_at.

    line_total is before any order-level discount, so the sum can exceed the order revenue when the
    POS gave a discount on the whole order.
    """
    branch_sql = " AND o.branch_id = :branch_id" if branch_id is not None else ""
    sql = f"""
        SELECT x.sku, x.name, SUM(x.quantity) AS quantity, SUM(x.line_total) AS revenue, MAX(x.at) AS last_at
        FROM (
            SELECT i.sku_snapshot AS sku, i.product_name_snapshot AS name, i.quantity, i.line_total, o.paid_at AS at
            FROM sales_orders o
            JOIN branches b ON b.branch_id = o.branch_id AND b.store_id = :store_id
            JOIN sales_order_items i ON i.sales_order_id = o.sales_order_id
            WHERE o.status = 'PAID' AND o.paid_at >= :start AND o.paid_at < :end{branch_sql}
            UNION ALL
            SELECT i.sku_snapshot, i.product_name_snapshot, i.quantity, i.line_total, o.fulfilled_at
            FROM preorders o
            JOIN branches b ON b.branch_id = o.branch_id AND b.store_id = :store_id
            JOIN preorder_items i ON i.preorder_id = o.preorder_id
            WHERE o.status = 'FULFILLED' AND o.payment_status <> 'REFUNDED'
              AND o.fulfilled_at >= :start AND o.fulfilled_at < :end{branch_sql}
        ) x
        GROUP BY x.sku, x.name"""
    params = {"store_id": store_id, "start": start_utc, "end": end_utc, "branch_id": branch_id}
    return list((await db.execute(text(sql), params)).mappings().all())


async def branch_label(db: AsyncSession, branch_id: int) -> tuple[str, str] | None:
    """(name, branch_code) of one branch, for the export file."""
    row = (await db.execute(text("SELECT name, branch_code FROM branches WHERE branch_id = :b"), {"b": branch_id})).first()
    return (row[0], row[1]) if row else None

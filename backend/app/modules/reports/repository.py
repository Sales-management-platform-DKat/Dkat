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

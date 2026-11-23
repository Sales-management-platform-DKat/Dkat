"""Seed revenue data for GET /reports/revenue (idempotent: order codes SEED-RV-*). Run after seed_auth.

Run from backend/:  python -m scripts.seed_sales

Timestamps are written in UTC, like the POS / pre-order services do (UTC_TIMESTAMP()).
Each row tests one rule (VN = Vietnam time, UTC+7):

  code   branch amount   state                      paid/fulfilled (UTC)   VN day / note
  R01    CN01   100000   sale PAID                  2025-12-31 17:30       2026-01-01 00:30 -> year 2026
  R02    CN01   200000   sale PAID                  2025-12-31 16:30       2025-12-31 23:30 -> year 2025
  R03    CN01   150000   sale PAID                  2026-10-31 17:30       2026-11-01 00:30 -> November
  R04    CN02   250000   sale PAID                  2026-11-01 16:59       2026-11-01 23:59
  R05    CN02   300000   sale PAID                  2026-11-01 17:00       2026-11-02 00:00 (Monday)
  R06    CN01   120000   sale PAID                  2026-11-22 16:00       Sun 2026-11-22 23:00 -> week of 16/11
  R07    CN01   180000   sale PAID                  2026-11-22 17:10       Mon 2026-11-23 00:10 -> week of 23/11
  R08    CN03   500000   sale PAID                  2026-11-10 03:00       2026-11-10 10:00
  P01    CN02   400000   pre-order FULFILLED        2026-11-15 05:00       2026-11-15 12:00
  P02    CN03   350000   pre-order FULFILLED        2026-11-30 18:00       2026-12-01 01:00 -> December
  X01    CN01   777000   sale CANCELLED (refunded)  2026-11-10 02:00       never counted
  X02    CN01   666000   sale PENDING               -                      never counted
  X03    CN01   888000   pre-order FULFILLED, payment REFUNDED  2026-11-12 03:00   never counted
  X04    CN01   555000   pre-order READY (paid, not picked up)              never counted
  X05    CN02   444000   pre-order CANCELLED                                never counted

Every order also has snapshot lines (ITEMS) for GET /reports/top-products; the line totals add up to
the order amount. SP-MAU-01-M was sold in 2025 under an older name: the newest snapshot name wins.
Lines are added to seed orders that have none, so re-running on an older seed backfills them.
"""
import asyncio

from sqlalchemy import text

from app.db.session import close_engine, standalone_transaction

# code, branch, amount, status, paid_at (UTC), payment method, payment status
SALES = [
    ("R01", "CN01", 100000, "PAID", "2025-12-31 17:30:00", "CASH", "SUCCESS"),
    ("R02", "CN01", 200000, "PAID", "2025-12-31 16:30:00", "CARD", "SUCCESS"),
    ("R03", "CN01", 150000, "PAID", "2026-10-31 17:30:00", "CASH", "SUCCESS"),
    ("R04", "CN02", 250000, "PAID", "2026-11-01 16:59:00", "BANK_TRANSFER", "SUCCESS"),
    ("R05", "CN02", 300000, "PAID", "2026-11-01 17:00:00", "CASH", "SUCCESS"),
    ("R06", "CN01", 120000, "PAID", "2026-11-22 16:00:00", "CASH", "SUCCESS"),
    ("R07", "CN01", 180000, "PAID", "2026-11-22 17:10:00", "CARD", "SUCCESS"),
    ("R08", "CN03", 500000, "PAID", "2026-11-10 03:00:00", "CASH", "SUCCESS"),
    ("X01", "CN01", 777000, "CANCELLED", "2026-11-10 02:00:00", "CASH", "REFUNDED"),
    ("X02", "CN01", 666000, "PENDING", None, None, None),
]
# code, branch, amount, status, payment_status, fulfilled_at (UTC)
PREORDERS = [
    ("P01", "CN02", 400000, "FULFILLED", "PAID", "2026-11-15 05:00:00"),
    ("P02", "CN03", 350000, "FULFILLED", "PAID", "2026-11-30 18:00:00"),
    ("X03", "CN01", 888000, "FULFILLED", "REFUNDED", "2026-11-12 03:00:00"),
    ("X04", "CN01", 555000, "READY", "PAID", None),
    ("X05", "CN02", 444000, "CANCELLED", "UNPAID", None),
]
S, M = "Áo thun mẫu - Size S", "Áo thun mẫu - Size M"
XANH, DO, QUAN = "Áo sơ mi mẫu - Xanh M", "Áo sơ mi mẫu - Đỏ L", "Quần kaki mẫu - Đen M"
# order code -> [(sku, product name snapshot, unit price, quantity)]
ITEMS = {
    "R01": [("SP-MAU-01-S", S, 50000, 2)],
    "R02": [("SP-MAU-01-M", "Áo thun mẫu - M (tên cũ)", 200000, 1)],
    "R03": [("SP-MAU-01-S", S, 150000, 1)],
    "R04": [("SP-MAU-02-XANH-M", XANH, 250000, 1)],
    "R05": [("SP-MAU-01-S", S, 150000, 2)],
    "R06": [("SP-MAU-01-M", M, 120000, 1)],
    "R07": [("SP-MAU-03-M", QUAN, 180000, 1)],
    "R08": [("SP-MAU-02-XANH-M", XANH, 250000, 1), ("SP-MAU-01-S", S, 150000, 1), ("SP-MAU-01-M", M, 100000, 1)],
    "X01": [("SP-MAU-02-XANH-M", XANH, 259000, 3)],
    "X02": [("SP-MAU-01-S", S, 666000, 1)],
    "P01": [("SP-MAU-02-DO-L", DO, 280000, 1), ("SP-MAU-01-S", S, 120000, 1)],
    "P02": [("SP-MAU-03-M", QUAN, 350000, 1)],
    "X03": [("SP-MAU-03-M", QUAN, 444000, 2)],
    "X04": [("SP-MAU-01-S", S, 555000, 1)],
    "X05": [("SP-MAU-02-DO-L", DO, 444000, 1)],
}


async def main() -> None:
    async with standalone_transaction() as db:
        store = (await db.execute(text("SELECT store_id FROM users WHERE username = 'owner01'"))).scalar()
        if store is None:
            raise SystemExit("Run python -m scripts.seed_auth first")
        staff = (await db.execute(text("SELECT user_id FROM users WHERE username = 'staff01'"))).scalar_one()
        branches = dict((await db.execute(text("SELECT branch_code, branch_id FROM branches WHERE store_id = :s"), {"s": store})).all())

        created = 0
        for code, branch, amount, status, paid_at, method, pay_status in SALES:
            result = await db.execute(
                text(
                    """INSERT IGNORE INTO sales_orders (order_code, branch_id, created_by, subtotal, discount_amount,
                       total_amount, status, created_at, paid_at)
                       VALUES (:c, :b, :u, :t, 0, :t, :st, COALESCE(:at, UTC_TIMESTAMP()), :paid)"""
                ),
                {"c": f"SEED-RV-{code}", "b": branches[branch], "u": staff, "t": amount, "st": status, "at": paid_at,
                 "paid": paid_at if status == "PAID" else None},
            )
            if result.rowcount and method:
                order_id = result.lastrowid
                await db.execute(
                    text("""INSERT INTO payments (sales_order_id, payment_method, amount, status, confirmed_by, confirmed_at)
                            VALUES (:o, :m, :a, :st, :u, :at)"""),
                    {"o": order_id, "m": method, "a": amount, "st": pay_status, "u": staff, "at": paid_at},
                )
            created += result.rowcount

        for code, branch, amount, status, pay_status, fulfilled_at in PREORDERS:
            result = await db.execute(
                text(
                    """INSERT IGNORE INTO preorders (preorder_code, branch_id, customer_name, customer_phone, total_amount,
                       payment_status, status, created_at, fulfilled_at)
                       VALUES (:c, :b, 'Khách seed doanh thu', '0500000001', :t, :ps, :st, COALESCE(:at, UTC_TIMESTAMP()), :at)"""
                ),
                {"c": f"SEED-RV-{code}", "b": branches[branch], "t": amount, "ps": pay_status, "st": status, "at": fulfilled_at},
            )
            created += result.rowcount

        # Snapshot lines (also backfills seed orders created before ITEMS existed)
        variants = dict((await db.execute(text("SELECT sku, variant_id FROM product_variants WHERE sku LIKE 'SP-MAU-%'"))).all())
        lines = 0
        for code, items in ITEMS.items():
            for table, id_col, item_table in (
                ("sales_orders", "sales_order_id", "sales_order_items"),
                ("preorders", "preorder_id", "preorder_items"),
            ):
                code_col = "order_code" if table == "sales_orders" else "preorder_code"
                order_id = (await db.execute(text(f"SELECT {id_col} FROM {table} WHERE {code_col} = :c"), {"c": f"SEED-RV-{code}"})).scalar()
                if order_id is None:
                    continue
                if (await db.execute(text(f"SELECT 1 FROM {item_table} WHERE {id_col} = :o LIMIT 1"), {"o": order_id})).first():
                    continue
                for sku, name, price, qty in items:
                    extra_cols, extra_vals = ("", "") if item_table == "sales_order_items" else (", allocated_quantity", ", 0")
                    await db.execute(
                        text(f"""INSERT INTO {item_table} ({id_col}, variant_id, product_name_snapshot, sku_snapshot, unit_price,
                                 quantity, line_total{extra_cols}) VALUES (:o, :v, :n, :sku, :p, :q, :lt{extra_vals})"""),
                        {"o": order_id, "v": variants[sku], "n": name, "sku": sku, "p": price, "q": qty, "lt": price * qty},
                    )
                    lines += 1
        print(f"{lines} snapshot lines added")
    await close_engine()
    print(f"Done. {created} revenue seed orders created (existing ones skipped).")


if __name__ == "__main__":
    asyncio.run(main())

"""Data consistency checks (NFR-04, NFR-11): reports and stock against the raw database. Read-only.

    python -m scripts.check_reconciliation          # any database configured in backend/.env (no server needed)

1. Revenue: /reports/revenue (day / week / month), /reports/summary for every branch and the whole store
   = hand-written SQL: sales orders PAID by paid_at + pre-orders FULFILLED (not REFUNDED) by fulfilled_at,
   bucketed by Vietnam day (UTC+7). Last 30 days.
2. Stock: for every inventory row, quantity = opening stock (0, rows are created empty) + SUM(movements).
3. Movements = documents: SALE movements = -(items of orders that were paid), refund movements = +(items of
   refunded orders), PREORDER_FULFILLMENT = -(items of fulfilled pre-orders).
4. Reserved stock in /inventory = SUM(allocated_quantity) of open pre-orders (WAITING_STOCK, READY, NOTIFIED);
   available = quantity - reserved; quantity >= reserved.
Exit code 1 on any mismatch.
"""
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.core.config import settings

VN = timezone(timedelta(hours=7))
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}", flush=True)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    settings.NOTIFY_RETRY_ENABLED = False
    from fastapi.testclient import TestClient

    from app.db.session import engine
    from app.main import app

    def q(sql, **p):
        with engine.connect() as db:
            return db.execute(text(sql), p).mappings().all()

    store = q("SELECT store_id FROM stores ORDER BY store_id LIMIT 1")[0]["store_id"]
    owner = q("SELECT username FROM users WHERE store_id=:s AND role='OWNER' LIMIT 1", s=store)[0]["username"]
    branches = [r["branch_id"] for r in q("SELECT branch_id FROM branches WHERE store_id=:s ORDER BY branch_id", s=store)]
    today = datetime.now(VN).date()
    start = today - timedelta(days=29)

    # ---- independent revenue: one row per paid sale / fulfilled pre-order, with its Vietnam day
    rows = q("""SELECT o.branch_id, o.total_amount AS amount, o.paid_at AS at, 'SALE' AS kind
                FROM sales_orders o JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:s WHERE o.status='PAID'
                UNION ALL
                SELECT p.branch_id, p.total_amount, p.fulfilled_at, 'PREORDER'
                FROM preorders p JOIN branches b ON b.branch_id=p.branch_id AND b.store_id=:s
                WHERE p.status='FULFILLED' AND p.payment_status <> 'REFUNDED'""", s=store)
    ledger = [(r["branch_id"], Decimal(r["amount"]), (r["at"] + timedelta(hours=7)).date(), r["kind"]) for r in rows]

    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": owner, "password": sys.argv[1] if len(sys.argv) > 1 else "DKat@Demo2026"})
        if login.status_code != 200:
            print(f"Không đăng nhập được OWNER {owner}: {login.text[:200]}")
            return 1
        auth = {"Authorization": "Bearer " + login.json()["access_token"]}

        for branch in [None] + branches:
            label = "toàn cửa hàng" if branch is None else f"chi nhánh {branch}"
            mine = [l for l in ledger if (branch is None or l[0] == branch) and start <= l[2] <= today]
            expected_total = sum((l[1] for l in mine), Decimal(0))
            by_day = defaultdict(Decimal)
            for l in mine:
                by_day[l[2]] += l[1]
            params = {"from": str(start), "to": str(today), "granularity": "day"}
            if branch is not None:
                params["branchId"] = branch
            rep = client.get("/api/v1/reports/revenue", headers=auth, params=params).json()
            got_days = {date.fromisoformat(p["period"]): Decimal(str(p["revenue"])) for p in rep["points"]}
            wrong = [(d, got_days.get(d), v) for d, v in by_day.items() if got_days.get(d) != v]
            extra = [d for d, v in got_days.items() if v and d not in by_day]
            check(f"Doanh thu theo ngày, {label}, {start}..{today}",
                  Decimal(str(rep["totals"]["revenue"])) == expected_total and not wrong and not extra and len(rep["points"]) == 30,
                  f"báo cáo {rep['totals']['revenue']:,.0f} đ / {rep['totals']['orderCount']} đơn; SQL {expected_total:,.0f} đ / {len(mine)} đơn; "
                  f"ngày lệch {wrong[:3]}{' ...' if len(wrong) > 3 else ''}; ngày thừa {extra[:3]}")
            check(f"Tách doanh thu bán tại quầy / đặt trước, {label}",
                  Decimal(str(rep["totals"]["salesRevenue"])) == sum((l[1] for l in mine if l[3] == "SALE"), Decimal(0))
                  and Decimal(str(rep["totals"]["preorderRevenue"])) == sum((l[1] for l in mine if l[3] == "PREORDER"), Decimal(0))
                  and rep["totals"]["orderCount"] == len(mine),
                  f"quầy {rep['totals']['salesRevenue']:,.0f} / đặt trước {rep['totals']['preorderRevenue']:,.0f} / {rep['totals']['orderCount']} đơn")
            for granularity in ("week", "month"):
                r2 = client.get("/api/v1/reports/revenue", headers=auth, params={**params, "granularity": granularity}).json()
                total = sum((Decimal(str(p["revenue"])) for p in r2["points"]), Decimal(0))
                check(f"Doanh thu theo {granularity}, {label}: tổng các kỳ = tổng theo ngày",
                      total == expected_total and Decimal(str(r2["totals"]["revenue"])) == expected_total, f"{total:,.0f} đ")
            sp = {"from": str(start), "to": str(today), **({"branchId": branch} if branch else {})}
            summary = client.get("/api/v1/reports/summary", headers=auth, params=sp).json()
            avg = (expected_total / len(mine)).quantize(Decimal("0.01")) if mine else Decimal(0)
            check(f"Thẻ Tổng quan (summary), {label}",
                  Decimal(str(summary["revenue"]["value"])) == expected_total and summary["orderCount"]["value"] == len(mine)
                  and abs(Decimal(str(summary["averageOrderValue"]["value"])) - avg) <= Decimal("0.01"),
                  f"doanh thu {summary['revenue']['value']:,.0f}, số đơn {summary['orderCount']['value']}, TB {summary['averageOrderValue']['value']:,.2f} (SQL TB {avg:,.2f})")

        # ---- stock = opening (0) + movements
        inv = q("""SELECT i.inventory_id, i.branch_id, i.variant_id, v.sku, i.quantity,
                          COALESCE((SELECT SUM(m.quantity_change) FROM inventory_movements m WHERE m.inventory_id=i.inventory_id), 0) AS moved
                   FROM inventory i JOIN product_variants v ON v.variant_id=i.variant_id
                   JOIN branches b ON b.branch_id=i.branch_id AND b.store_id=:s""", s=store)
        bad = [(r["branch_id"], r["sku"], r["quantity"], int(r["moved"])) for r in inv if r["quantity"] != int(r["moved"])]
        check("Tồn kho = tồn đầu (0) + tổng biến động, mọi dòng tồn",
              not bad, f"{len(inv)} dòng tồn, tổng tồn {sum(r['quantity'] for r in inv)}, tổng biến động {sum(int(r['moved']) for r in inv)}; lệch: {bad[:5]}")
        by_type = q("""SELECT m.movement_type t, COALESCE(m.reference_type,'') rt, SUM(m.quantity_change) n, COUNT(*) c
                       FROM inventory_movements m JOIN inventory i ON i.inventory_id=m.inventory_id
                       JOIN branches b ON b.branch_id=i.branch_id AND b.store_id=:s GROUP BY m.movement_type, m.reference_type""", s=store)
        print("      biến động theo loại: " + "; ".join(f"{r['t']}/{r['rt'] or '-'}: {int(r['n'])} ({r['c']} dòng)" for r in by_type))

        # ---- movements = documents
        sold = q("""SELECT COALESCE(SUM(i.quantity),0) n FROM sales_orders o JOIN sales_order_items i ON i.sales_order_id=o.sales_order_id
                    JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:s WHERE o.paid_at IS NOT NULL""", s=store)[0]["n"]
        refunded = q("""SELECT COALESCE(SUM(i.quantity),0) n FROM sales_orders o JOIN sales_order_items i ON i.sales_order_id=o.sales_order_id
                        JOIN branches b ON b.branch_id=o.branch_id AND b.store_id=:s
                        WHERE EXISTS (SELECT 1 FROM payments p WHERE p.sales_order_id=o.sales_order_id AND p.status='REFUNDED')""", s=store)[0]["n"]
        fulfilled = q("""SELECT COALESCE(SUM(i.quantity),0) n FROM preorders p JOIN preorder_items i ON i.preorder_id=p.preorder_id
                         JOIN branches b ON b.branch_id=p.branch_id AND b.store_id=:s WHERE p.status='FULFILLED'""", s=store)[0]["n"]
        mv = defaultdict(int)
        for r in by_type:
            mv[r["t"]] += int(r["n"])
        # the sales module books a refund's restock as ADJUSTMENT with reference_type SALES_ORDER
        # (stocktake adjustments have no sales-order reference)
        sale_mv = sum(int(r["n"]) for r in by_type if r["t"] == "SALE")
        refund_mv = sum(int(r["n"]) for r in by_type if r["t"] == "ADJUSTMENT" and r["rt"] == "SALES_ORDER")
        check("Biến động bán = số lượng các đơn đã thanh toán; hoàn kho = số lượng các đơn đã hoàn",
              -sale_mv == int(sold) and refund_mv == int(refunded),
              f"SALE {sale_mv} vs đơn đã thanh toán {int(sold)}; hoàn kho {refund_mv} vs đơn đã hoàn {int(refunded)}")
        check("Biến động giao đặt trước = số lượng các đơn đặt trước đã giao",
              -mv["PREORDER_FULFILLMENT"] == int(fulfilled), f"PREORDER_FULFILLMENT {mv['PREORDER_FULFILLMENT']} vs đã giao {int(fulfilled)}")

        # ---- reserved / available
        held = {(r["branch_id"], r["variant_id"]): int(r["n"]) for r in q(
            """SELECT p.branch_id, i.variant_id, SUM(i.allocated_quantity) n FROM preorders p JOIN preorder_items i ON i.preorder_id=p.preorder_id
               WHERE p.status IN ('WAITING_STOCK','READY','NOTIFIED') GROUP BY p.branch_id, i.variant_id""")}
        stale = q("""SELECT COUNT(*) n FROM preorders p JOIN preorder_items i ON i.preorder_id=p.preorder_id
                     WHERE p.status IN ('FULFILLED','CANCELLED','EXPIRED') AND i.allocated_quantity <> 0""")[0]["n"]
        api_rows = []
        for branch in branches:
            api_rows += client.get("/api/v1/inventory", headers=auth, params={"branchId": branch, "page": 1, "size": 100}).json()
        mism = [(r["branchId"], r["sku"], r["quantity"], r["reserved"], r["available"], held.get((r["branchId"], r["variantId"]), 0))
                for r in api_rows if r["reserved"] != held.get((r["branchId"], r["variantId"]), 0)
                or r["available"] != r["quantity"] - r["reserved"] or r["quantity"] < r["reserved"]]
        check("Đã giữ = tổng phân bổ của đơn đặt trước đang mở; Khả dụng = Tồn thực - Đã giữ; không giữ quá tồn",
              not mism and stale == 0,
              f"{len(api_rows)} dòng, tổng đang giữ {sum(r['reserved'] for r in api_rows)}; lệch {mism[:5]}; đơn đã đóng còn phân bổ: {stale}")

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} phép đối chiếu khớp")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

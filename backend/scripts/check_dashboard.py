"""Reconcile GET /reports/summary and GET /reports/top-products (FR-06.5) with hand-written SQL and
with values computed by hand from scripts/seed_sales.py. Also checks the permission rules.

Requires: seed_auth, seed_catalog, database/04 + 06 SQL, seed_sales.
Run from backend/:  python -m scripts.check_dashboard      (exit code 1 on any failure)
"""
import asyncio
import sys

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.db.session import close_engine, engine
from app.main import create_app

API = settings.API_V1_PREFIX
results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name, detail))


async def hand_totals(conn, utc_from: str, utc_to: str, code: str | None) -> tuple[float, int]:
    """Hand-written: revenue and order count of PAID sales + FULFILLED, not refunded pre-orders."""
    b = "AND b.branch_code = :code" if code else ""
    row = (
        await conn.execute(
            text(f"""
            SELECT SUM(t), SUM(n) FROM (
              SELECT COALESCE(SUM(so.total_amount), 0) t, COUNT(*) n FROM sales_orders so JOIN branches b ON b.branch_id = so.branch_id
               WHERE so.status = 'PAID' AND so.paid_at >= :f AND so.paid_at < :u {b}
              UNION ALL
              SELECT COALESCE(SUM(po.total_amount), 0), COUNT(*) FROM preorders po JOIN branches b ON b.branch_id = po.branch_id
               WHERE po.status = 'FULFILLED' AND po.payment_status <> 'REFUNDED' AND po.fulfilled_at >= :f AND po.fulfilled_at < :u {b}
            ) x"""),
            {"f": utc_from, "u": utc_to, "code": code},
        )
    ).one()
    return float(row[0]), int(row[1])


async def hand_top(conn, utc_from: str, utc_to: str, code: str | None) -> dict[str, tuple[int, float]]:
    """Hand-written: {sku: (quantity, revenue)} from the snapshot lines of counted orders."""
    b = "AND b.branch_code = :code" if code else ""
    rows = (
        await conn.execute(
            text(f"""
            SELECT sku, SUM(q), SUM(lt) FROM (
              SELECT i.sku_snapshot sku, i.quantity q, i.line_total lt FROM sales_order_items i
                JOIN sales_orders so ON so.sales_order_id = i.sales_order_id JOIN branches b ON b.branch_id = so.branch_id
               WHERE so.status = 'PAID' AND so.paid_at >= :f AND so.paid_at < :u {b}
              UNION ALL
              SELECT i.sku_snapshot, i.quantity, i.line_total FROM preorder_items i
                JOIN preorders po ON po.preorder_id = i.preorder_id JOIN branches b ON b.branch_id = po.branch_id
               WHERE po.status = 'FULFILLED' AND po.payment_status <> 'REFUNDED' AND po.fulfilled_at >= :f AND po.fulfilled_at < :u {b}
            ) x GROUP BY sku"""),
            {"f": utc_from, "u": utc_to, "code": code},
        )
    ).all()
    return {sku: (int(q), float(r)) for sku, q, r in rows}


async def main() -> int:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c, engine.connect() as conn:
        br = dict((await conn.execute(text("SELECT branch_code, branch_id FROM branches"))).all())
        h = {}
        for role, user in {"OWNER": "owner01", "MANAGER": "manager01", "EMPLOYEE": "staff01"}.items():
            r = await c.post(f"{API}/auth/login", json={"username": user, "password": "Dkat@1234"})
            h[role] = {"Authorization": "Bearer " + r.json()["data"]["token"]}

        async def get(path, role, **params):
            r = await c.get(f"{API}/reports/{path}", headers=h[role], params=params)
            return r, (r.json()["data"] if r.status_code == 200 else {})

        # ---- 1. summary: API = hand SQL = seed
        cases = [
            # label, params, role, current UTC window, previous UTC window, code, seed (rev, count, prev rev, prev count), expected % (rev, count, aov)
            ("Tháng 11/2026, toàn chuỗi (kỳ trước = 0 -> null)", {"from": "2026-11-01", "to": "2026-11-30"}, "OWNER",
             ("2026-10-31 17:00:00", "2026-11-30 17:00:00"), ("2026-10-01 17:00:00", "2026-10-31 17:00:00"), None,
             (1900000, 7, 0, 0), (None, None, None)),
            ("Tháng 12/2026 so với 31 ngày trước, toàn chuỗi", {"from": "2026-12-01", "to": "2026-12-31"}, "OWNER",
             ("2026-11-30 17:00:00", "2026-12-31 17:00:00"), ("2026-10-30 17:00:00", "2026-11-30 17:00:00"), None,
             (350000, 1, 1900000, 7), (-81.6, -85.7, 28.9)),
            ("Tuần 23-29/11 so với 16-22/11, CN01 (MANAGER)", {"from": "2026-11-23", "to": "2026-11-29", "branchId": br["CN01"]}, "MANAGER",
             ("2026-11-22 17:00:00", "2026-11-29 17:00:00"), ("2026-11-15 17:00:00", "2026-11-22 17:00:00"), "CN01",
             (180000, 1, 120000, 1), (50.0, 0.0, 50.0)),
        ]
        for label, params, role, cur_w, prev_w, code, seed, pct in cases:
            r, d = await get("summary", role, **params)
            if r.status_code != 200:
                check(label, False, f"{r.status_code} {r.text[:150]}")
                continue
            hand_cur, hand_prev = await hand_totals(conn, *cur_w, code), await hand_totals(conn, *prev_w, code)
            api = (d["revenue"]["value"], d["orderCount"]["value"], d["revenue"]["previous"], d["orderCount"]["previous"])
            check(f"{label}: doanh thu & số đơn = SQL tay = seed", api == (*hand_cur, *hand_prev) == tuple(float(x) for x in seed),
                  f"api={api} sql={hand_cur}/{hand_prev} seed={seed}")
            aov = round(seed[0] / seed[1], 2) if seed[1] else 0
            check(f"{label}: giá trị TB/đơn", d["averageOrderValue"]["value"] == aov, f"{d['averageOrderValue']} != {aov}")
            got_pct = (d["revenue"]["changePercent"], d["orderCount"]["changePercent"], d["averageOrderValue"]["changePercent"])
            check(f"{label}: % thay đổi {pct}", got_pct == pct, str(got_pct))
        _, d = await get("summary", "OWNER", **{"from": "2026-11-01", "to": "2026-11-30"})
        check("Kỳ trước = cùng số ngày liền trước (02/10-31/10)", d["previousPeriod"] == {"dateFrom": "2026-10-02", "dateTo": "2026-10-31"}, str(d["previousPeriod"]))
        check("Tách doanh thu bán / đặt trước (1.500.000 + 400.000)", (d["salesRevenue"], d["preorderRevenue"]) == (1500000, 400000), str(d))

        # ---- 2. top products: API = hand SQL = seed
        nov = ("2026-10-31 17:00:00", "2026-11-30 17:00:00")
        r, d = await get("top-products", "OWNER", **{"from": "2026-11-01", "to": "2026-11-30"})
        api = [(i["sku"], i["quantity"], i["revenue"]) for i in d["items"]]
        seed_nov = [("SP-MAU-01-S", 5, 720000.0), ("SP-MAU-02-XANH-M", 2, 500000.0), ("SP-MAU-02-DO-L", 1, 280000.0),
                    ("SP-MAU-01-M", 2, 220000.0), ("SP-MAU-03-M", 1, 180000.0)]
        hand = await hand_top(conn, *nov, None)
        check("Top tháng 11 theo doanh thu = seed (thứ tự đúng)", api == seed_nov, str(api))
        check("Top tháng 11 = SQL tay (số lượng, doanh thu từng SKU)", {s: (q, rv) for s, q, rv in api} == hand, f"sql={hand}")
        check("Có rank, sku, tên snapshot, số lượng, doanh thu",
              d["items"] and set(d["items"][0]) == {"rank", "sku", "productName", "quantity", "revenue"} and [i["rank"] for i in d["items"]] == [1, 2, 3, 4, 5],
              str(d["items"][:1]))
        check("Tổng doanh thu top = doanh thu tháng (không có giảm giá)", sum(i["revenue"] for i in d["items"]) == 1900000, "")
        check("Đơn CANCELLED (X01: 3 x SP-MAU-02-XANH-M) không tính", dict((s, q) for s, q, _ in api)["SP-MAU-02-XANH-M"] == 2, str(api))
        _, d = await get("top-products", "OWNER", **{"from": "2026-11-01", "to": "2026-11-30", "sortBy": "quantity", "limit": 3})
        check("sortBy=quantity, limit=3 (hoà số lượng -> doanh thu cao trước)",
              [i["sku"] for i in d["items"]] == ["SP-MAU-01-S", "SP-MAU-02-XANH-M", "SP-MAU-01-M"], str([i["sku"] for i in d["items"]]))
        _, d = await get("top-products", "OWNER", **{"from": "2025-01-01", "to": "2026-12-31"})
        m = next(i for i in d["items"] if i["sku"] == "SP-MAU-01-M")
        check("Tên = snapshot mới nhất, gộp các tên cũ của cùng SKU", (m["productName"], m["quantity"], m["revenue"]) == ("Áo thun mẫu - Size M", 3, 420000), str(m))
        _, d = await get("top-products", "MANAGER", **{"from": "2026-11-01", "to": "2026-11-30", "branchId": br["CN02"]})
        api = [(i["sku"], i["quantity"], i["revenue"]) for i in d["items"]]
        hand = await hand_top(conn, *nov, "CN02")
        check("Top CN02 (MANAGER) = SQL tay = seed",
              api == [("SP-MAU-01-S", 3, 420000.0), ("SP-MAU-02-DO-L", 1, 280000.0), ("SP-MAU-02-XANH-M", 1, 250000.0)]
              and {s: (q, rv) for s, q, rv in api} == hand, f"api={api} sql={hand}")
        _, d = await get("top-products", "OWNER", **{"from": "2026-10-01", "to": "2026-10-15"})
        check("Kỳ không có đơn -> danh sách rỗng", d["items"] == [], str(d["items"]))

        # ---- 3. same permission rules as /reports/revenue, for both endpoints
        for path in ("summary", "top-products"):
            for role, params, status, label in [
                ("EMPLOYEE", {}, 403, "EMPLOYEE -> 403"),
                ("MANAGER", {}, 400, "MANAGER thiếu branchId -> 400"),
                ("MANAGER", {"branchId": br["CN03"]}, 403, "MANAGER branchId CN03 -> 403"),
                ("MANAGER", {"branchId": br["CN02"]}, 200, "MANAGER branchId CN02 -> 200"),
                ("OWNER", {}, 200, "OWNER toàn chuỗi (mặc định 30 ngày) -> 200"),
                ("OWNER", {"branchId": br["CN03"]}, 200, "OWNER từng chi nhánh -> 200"),
                ("OWNER", {"from": "2026-12-01", "to": "2026-11-01"}, 422, "from > to -> 422"),
            ]:
                r, _ = await get(path, role, **params)
                check(f"{path}: {label}", r.status_code == status, f"{r.status_code} {r.text[:100]}")
            r = await c.get(f"{API}/reports/{path}")
            check(f"{path}: không token -> 401", r.status_code == 401, str(r.status_code))
        for params, label in [({"limit": 0}, "limit = 0"), ({"limit": 51}, "limit > 50"), ({"sortBy": "price"}, "sortBy sai")]:
            r, _ = await get("top-products", "OWNER", **params)
            check(f"top-products: {label} -> 422", r.status_code == 422, str(r.status_code))
    await close_engine()

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}")
    failed = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))

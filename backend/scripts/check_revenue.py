"""Reconcile GET /reports/revenue with hand-written SQL and with the seed values (FR-06).

For each checkpoint three numbers must agree:
  API      the report endpoint
  SQL      an independent query written by hand with literal UTC boundaries (VN day = UTC 17:00 the day before)
  seed     the amount computed by hand from the table in scripts/seed_sales.py
Plus: CANCELLED / refunded / unfinished orders never count, zero-filled periods, week = Monday, permissions.

Requires: seed_auth, database/04 + 06 SQL, seed_sales.   Run from backend/:  python -m scripts.check_revenue
Prints a markdown table of the checkpoints (copied into docs/revenue-reconciliation.md). Exit 1 on failure.
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
table: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name, detail))


def vnd(amount) -> str:
    return "—" if amount is None else f"{amount:,.0f}".replace(",", ".")  # 2.350.000


async def manual_sql(conn, utc_from: str, utc_to: str, branch_code: str | None) -> float:
    """Hand-written query: PAID sales by paid_at + FULFILLED, not refunded pre-orders by fulfilled_at."""
    branch = "AND b.branch_code = :code" if branch_code else ""
    sql = f"""
        SELECT
          (SELECT COALESCE(SUM(so.total_amount), 0) FROM sales_orders so JOIN branches b ON b.branch_id = so.branch_id
            WHERE so.status = 'PAID' AND so.paid_at >= :f AND so.paid_at < :t {branch})
        + (SELECT COALESCE(SUM(po.total_amount), 0) FROM preorders po JOIN branches b ON b.branch_id = po.branch_id
            WHERE po.status = 'FULFILLED' AND po.payment_status <> 'REFUNDED'
              AND po.fulfilled_at >= :f AND po.fulfilled_at < :t {branch})"""
    return float((await conn.execute(text(sql), {"f": utc_from, "t": utc_to, "code": branch_code})).scalar_one())


# label, granularity, from, to, branch code, role, period to read, UTC window for the hand query, seed value
CHECKPOINTS = [
    ("Ngày 01/11/2026, toàn chuỗi", "day", "2026-11-01", "2026-11-03", None, "OWNER", "2026-11-01",
     ("2026-10-31 17:00:00", "2026-11-01 17:00:00"), 150000 + 250000),  # R03 (00:30 VN) + R04 (23:59 VN)
    ("Ngày 02/11/2026, toàn chuỗi", "day", "2026-11-01", "2026-11-03", None, "OWNER", "2026-11-02",
     ("2026-11-01 17:00:00", "2026-11-02 17:00:00"), 300000),  # R05 at exactly 00:00 VN
    ("Tuần 16-22/11/2026 (W47), CN01", "week", "2026-11-16", "2026-11-29", "CN01", "OWNER", "2026-W47",
     ("2026-11-15 17:00:00", "2026-11-22 17:00:00"), 120000),  # R06 Sunday 23:00 VN
    ("Tuần 23-29/11/2026 (W48), CN01", "week", "2026-11-16", "2026-11-29", "CN01", "OWNER", "2026-W48",
     ("2026-11-22 17:00:00", "2026-11-29 17:00:00"), 180000),  # R07 Monday 00:10 VN
    ("Tháng 11/2026, CN02 (MANAGER)", "month", "2026-11-01", "2026-11-30", "CN02", "MANAGER", "2026-11",
     ("2026-10-31 17:00:00", "2026-11-30 17:00:00"), 250000 + 300000 + 400000),  # R04 + R05 + P01
    ("Tháng 12/2026, CN03", "month", "2026-12-01", "2026-12-31", "CN03", "OWNER", "2026-12",
     ("2026-11-30 17:00:00", "2026-12-31 17:00:00"), 350000),  # P02 fulfilled 01:00 VN on 01/12
    ("Năm 2025, toàn chuỗi", "year", "2025-01-01", "2026-12-31", None, "OWNER", "2025",
     ("2024-12-31 17:00:00", "2025-12-31 17:00:00"), 200000),  # R02 only (R01 is already 2026 in VN)
    ("Năm 2026, toàn chuỗi", "year", "2025-01-01", "2026-12-31", None, "OWNER", "2026",
     ("2025-12-31 17:00:00", "2026-12-31 17:00:00"),
     100000 + 150000 + 250000 + 300000 + 120000 + 180000 + 500000 + 400000 + 350000),
]
EXCLUDED_AMOUNTS = {777000.0, 666000.0, 888000.0, 555000.0, 444000.0}  # X01..X05


async def main() -> int:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c, engine.connect() as conn:
        branches = dict((await conn.execute(text("SELECT branch_code, branch_id FROM branches"))).all())
        headers = {}
        for role, user in {"OWNER": "owner01", "MANAGER": "manager01", "EMPLOYEE": "staff01"}.items():
            r = await c.post(f"{API}/auth/login", json={"username": user, "password": "Dkat@1234"})
            headers[role] = {"Authorization": "Bearer " + r.json()["data"]["token"]}

        async def report(role, **params):
            r = await c.get(f"{API}/reports/revenue", headers=headers[role], params=params)
            return r, (r.json()["data"] if r.status_code == 200 else {})

        # ---- 1. checkpoints: API = hand SQL = seed
        table.append("| Mốc | API | Truy vấn tay | Seed tính tay | Khớp |")
        table.append("|---|---:|---:|---:|:-:|")
        for label, gran, f, t, code, role, period, (uf, ut), seed in CHECKPOINTS:
            params = {"granularity": gran, "from": f, "to": t}
            if code:
                params["branchId"] = branches[code]
            r, d = await report(role, **params)
            point = next((p for p in d.get("points", []) if p["period"] == period), None)
            api = point["revenue"] if point else None
            hand = await manual_sql(conn, uf, ut, code)
            ok = r.status_code == 200 and api == hand == float(seed)
            check(f"{label}: API = SQL tay = seed", ok, f"status={r.status_code} api={api} sql={hand} seed={seed}")
            table.append(f"| {label} | {vnd(api)} | {vnd(hand)} | {vnd(seed)} | {'✓' if ok else '✗'} |")

        # ---- 2. excluded orders + zero fill
        r, d = await report("OWNER", granularity="day", **{"from": "2026-11-01", "to": "2026-11-30"})
        pts = d["points"]
        check("Tháng 11 theo ngày: đủ 30 điểm liên tục", [p["period"] for p in pts] == [f"2026-11-{i:02d}" for i in range(1, 31)], str(len(pts)))
        check("Ngày không có đơn = 0 (vd. 05/11)", next(p for p in pts if p["period"] == "2026-11-05")["revenue"] == 0, "")
        month_hand = await manual_sql(conn, "2026-10-31 17:00:00", "2026-11-30 17:00:00", None)
        check("Tổng tháng 11 = SQL tay", d["totals"]["revenue"] == month_hand == 1900000.0, f"{d['totals']} sql={month_hand}")
        amounts = {p["revenue"] for p in pts} | {p["salesRevenue"] for p in pts} | {p["preorderRevenue"] for p in pts}
        check("Không xuất hiện đơn CANCELLED / PENDING / hoàn tiền / chưa nhận", not amounts & EXCLUDED_AMOUNTS, str(amounts & EXCLUDED_AMOUNTS))
        d10 = next(p for p in pts if p["period"] == "2026-11-10")
        check("10/11: chỉ R08 500000 (X01 CANCELLED 777000 bị loại)", d10["revenue"] == 500000 and d10["orderCount"] == 1, str(d10))
        d12 = next(p for p in pts if p["period"] == "2026-11-12")
        check("12/11: đặt trước FULFILLED nhưng REFUNDED không tính", d12["revenue"] == 0, str(d12))
        d15 = next(p for p in pts if p["period"] == "2026-11-15")
        check("15/11: tách doanh thu đặt trước", d15["preorderRevenue"] == 400000 and d15["salesRevenue"] == 0, str(d15))

        _, d = await report("OWNER", granularity="week", **{"from": "2026-11-18", "to": "2026-11-24"})
        weeks = [(p["period"], p["periodStart"], p["periodEnd"]) for p in d["points"]]
        check("Tuần bắt đầu thứ Hai (W47: 16-22/11, W48: 23-29/11)",
              weeks == [("2026-W47", "2026-11-16", "2026-11-22"), ("2026-W48", "2026-11-23", "2026-11-29")], str(weeks))
        _, d = await report("OWNER", granularity="month", **{"from": "2026-01-01", "to": "2026-12-31"})
        check("Năm 2026 theo tháng: 12 điểm, tháng trống = 0",
              len(d["points"]) == 12 and d["points"][2]["revenue"] == 0 and d["points"][0]["revenue"] == 100000, str([p["revenue"] for p in d["points"]]))
        r, d = await report("OWNER")
        check("Mặc định: theo ngày, 30 điểm đến hôm nay", r.status_code == 200 and len(d["points"]) == 30, str(r.status_code))

        # ---- 3. permissions and validation
        for role, params, status, label in [
            ("EMPLOYEE", {}, 403, "EMPLOYEE -> 403"),
            ("EMPLOYEE", {"branchId": branches["CN01"]}, 403, "EMPLOYEE có branchId -> 403"),
            ("MANAGER", {}, 400, "MANAGER thiếu branchId -> 400"),
            ("MANAGER", {"branchId": branches["CN03"]}, 403, "MANAGER branchId CN03 (không phân công) -> 403"),
            ("MANAGER", {"branchId": branches["CN01"]}, 200, "MANAGER branchId CN01 -> 200"),
            ("OWNER", {}, 200, "OWNER toàn chuỗi -> 200"),
            ("OWNER", {"branchId": branches["CN03"]}, 200, "OWNER từng chi nhánh -> 200"),
            ("OWNER", {"branchId": 999999}, 404, "OWNER chi nhánh không tồn tại -> 404"),
            ("OWNER", {"granularity": "hour"}, 422, "granularity sai -> 422"),
            ("OWNER", {"from": "2026-12-01", "to": "2026-11-01"}, 422, "from > to -> 422"),
            ("OWNER", {"granularity": "day", "from": "2020-01-01", "to": "2026-11-24"}, 422, "quá 400 kỳ -> 422"),
        ]:
            r, _ = await report(role, **params)
            check(label, r.status_code == status, f"{r.status_code} {r.text[:120]}")
        r = await c.get(f"{API}/reports/revenue")
        check("Không token -> 401", r.status_code == 401, str(r.status_code))
    await close_engine()

    print("\n".join(table))
    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}")
    failed = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))

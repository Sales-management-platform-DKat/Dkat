"""Check GET /reports/revenue/export (CSV for Excel) against GET /reports/revenue.

Requires seed_auth + seed_sales (+ database/04, 06 SQL).  Run from backend/:
    python -m scripts.check_revenue_export            (exit code 1 on any failure)
    python -m scripts.check_revenue_export --save X   also writes the November CSV to file X (to open in Excel)
"""
import argparse
import asyncio
import csv
import io
import sys
from datetime import date

import httpx

from app.core.config import settings
from app.db.session import close_engine
from app.main import create_app
from app.modules.reports.export import HEADERS, revenue_csv
from app.modules.reports.schemas import RevenuePoint, RevenueReportOut, RevenueTotals

API = settings.API_V1_PREFIX
results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((bool(ok), name, detail))


def parse(content: bytes, delimiter: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig")), delimiter=delimiter))


def money(v: float) -> str:
    return str(int(round(v)))


async def main(save: str | None) -> int:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as c:
        h, branches = {}, {}
        for role, user in {"OWNER": "owner01", "MANAGER": "manager01", "EMPLOYEE": "staff01"}.items():
            r = await c.post(f"{API}/auth/login", json={"username": user, "password": "Dkat@1234"})
            h[role] = {"Authorization": "Bearer " + r.json()["data"]["token"]}
        for b in (await c.get(f"{API}/branches", headers=h["OWNER"])).json()["data"]:
            branches[b["branchCode"]] = b["id"]

        async def both(role, **params):
            csv_r = await c.get(f"{API}/reports/revenue/export", headers=h[role], params=params)
            json_r = await c.get(f"{API}/reports/revenue", headers=h[role], params={k: v for k, v in params.items() if k != "delimiter"})
            return csv_r, (json_r.json()["data"] if json_r.status_code == 200 else None)

        # ---- 1. whole chain, November by day
        r, report = await both("OWNER", granularity="day", **{"from": "2026-11-01", "to": "2026-11-30"})
        check("200, text/csv; charset=utf-8", r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "utf-8" in r.headers["content-type"], str(r.headers.get("content-type")))
        check("Tải về dạng file: doanh-thu_day_2026-11-01_2026-11-30_toan-chuoi.csv",
              r.headers.get("content-disposition") == 'attachment; filename="doanh-thu_day_2026-11-01_2026-11-30_toan-chuoi.csv"', str(r.headers.get("content-disposition")))
        check("Bắt đầu bằng BOM UTF-8 (EF BB BF) để Excel đọc đúng tiếng Việt", r.content[:3] == b"\xef\xbb\xbf", r.content[:3].hex())
        check("Xuống dòng CRLF", b"\r\n" in r.content)
        rows = parse(r.content)
        check("Dòng tiêu đề tiếng Việt", rows[0] == HEADERS, str(rows[0]))
        data, total = rows[1:-1], rows[-1]
        check("30 dòng ngày + 1 dòng Tổng cộng", len(data) == 30 and total[1] == "Tổng cộng", f"{len(data)} {total[:2]}")
        same = all(
            row == ["Toàn chuỗi", f"Ngày {p['period']}", p["periodStart"], p["periodEnd"], money(p["revenue"]), money(p["salesRevenue"]),
                    money(p["preorderRevenue"]), str(p["orderCount"]), str(p["salesCount"]), str(p["preorderCount"])]
            for row, p in zip(data, report["points"])
        )
        check("Từng dòng khớp API JSON /reports/revenue (cùng logic)", same, f"{data[0]} vs {report['points'][0]}")
        t = report["totals"]
        check("Dòng Tổng cộng khớp totals (1900000, 7 đơn)",
              total[4:8] == [money(t["revenue"]), money(t["salesRevenue"]), money(t["preorderRevenue"]), str(t["orderCount"])] and total[4] == "1900000",
              str(total))
        check("Số tiền là số nguyên thuần (không dấu chấm/phẩy phân cách)", all(cell.isdigit() for row in data for cell in row[4:]), str(data[0]))
        if save:
            with open(save, "wb") as f:
                f.write(r.content)

        # ---- 2. one branch (MANAGER), week; semicolon
        r, report = await both("MANAGER", granularity="month", branchId=branches["CN02"], **{"from": "2026-11-01", "to": "2026-11-30"})
        rows = parse(r.content)
        check("MANAGER xuất chi nhánh được phân công (CN02) -> 200, tên chi nhánh, file _CN02",
              r.status_code == 200 and rows[1][0] == "Chi nhánh Cầu Giấy" and rows[1][1] == "Tháng 2026-11" and rows[1][4] == "950000"
              and r.headers["content-disposition"].endswith('_CN02.csv"'), f"{r.status_code} {rows[1] if len(rows) > 1 else rows}")
        r2, _ = await both("MANAGER", granularity="month", branchId=branches["CN02"], delimiter="semicolon", **{"from": "2026-11-01", "to": "2026-11-30"})
        check("delimiter=semicolon -> cùng dữ liệu, phân cách bằng ;", parse(r2.content, ";") == rows and b";" in r2.content, r2.content.decode("utf-8-sig")[:120])
        r, _ = await both("OWNER", granularity="week", **{"from": "2026-11-16", "to": "2026-11-29"})
        check("Tuần: nhãn 'Tuần 2026-W47', 'Tuần 2026-W48'", [row[1] for row in parse(r.content)[1:-1]] == ["Tuần 2026-W47", "Tuần 2026-W48"], str(parse(r.content)))

        # ---- 3. same permission / validation rules as /reports/revenue (JSON errors)
        for role, params, status, label in [
            ("EMPLOYEE", {}, 403, "EMPLOYEE -> 403"),
            ("MANAGER", {}, 400, "MANAGER thiếu branchId -> 400"),
            ("MANAGER", {"branchId": branches["CN03"]}, 403, "MANAGER chi nhánh không phân công -> 403"),
            ("OWNER", {"granularity": "hour"}, 422, "granularity sai -> 422"),
            ("OWNER", {"from": "2026-12-01", "to": "2026-11-01"}, 422, "from > to -> 422"),
            ("OWNER", {"delimiter": "tab"}, 422, "delimiter sai -> 422"),
        ]:
            r = await c.get(f"{API}/reports/revenue/export", headers=h[role], params=params)
            check(f"{label} (lỗi JSON như API doanh thu)", r.status_code == status and r.headers["content-type"].startswith("application/json"), str(r.status_code))
        r = await c.get(f"{API}/reports/revenue/export")
        check("Không token -> 401", r.status_code == 401)
    await close_engine()

    # ---- 4. CSV formula injection (branch names are user input)
    report = RevenueReportOut(granularity="day", date_from=date(2026, 1, 1), date_to=date(2026, 1, 1), branch_id=1, timezone="x",
                              totals=RevenueTotals(revenue=0, sales_revenue=0, preorder_revenue=0, order_count=0),
                              points=[RevenuePoint(period="2026-01-01", period_start=date(2026, 1, 1), period_end=date(2026, 1, 1), revenue=0,
                                                   sales_revenue=0, preorder_revenue=0, order_count=0, sales_count=0, preorder_count=0)])
    cell = parse(revenue_csv(report, '=HYPERLINK("http://evil")'))[1][0]
    check("Chặn chèn công thức Excel (=, +, -, @ -> thêm ')", cell.startswith("'="), cell)

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}")
    failed = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--save")
    sys.exit(asyncio.run(main(p.parse_args().save)))

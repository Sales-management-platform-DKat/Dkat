"""CSV export of the revenue report (FR-06): the same data as GET /reports/revenue.

Format chosen for Excel:
- UTF-8 WITH BOM: Excel only detects UTF-8 (Vietnamese accents) when the file starts with a BOM.
- Delimiter "," by default; "semicolon" for Windows regional settings whose list separator is ";"
  (e.g. some vi-VN setups), otherwise Excel puts every row in one column. No "sep=" line: Excel then
  ignores the BOM and the accents break.
- Money as plain integers (1900000): no thousands separator / decimal point that a locale could misread.
- Dates as ISO yyyy-mm-dd (Excel recognises them in every locale). CRLF line endings.
- Text cells that start with = + - @ are prefixed with ' (CSV formula injection: branch names are user input).
"""
import csv
import io
from datetime import date

from app.modules.reports.schemas import RevenueReportOut

DELIMITERS = {"comma": ",", "semicolon": ";"}
GRANULARITY_LABEL = {"day": "Ngày", "week": "Tuần", "month": "Tháng", "year": "Năm"}
HEADERS = [
    "Chi nhánh", "Kỳ", "Từ ngày", "Đến ngày", "Doanh thu (VND)", "Doanh thu bán hàng (VND)",
    "Doanh thu đặt trước (VND)", "Số đơn", "Số đơn bán", "Số đơn đặt trước",
]


def _money(value: float) -> str:
    return str(int(round(value))) if abs(value - round(value)) < 0.005 else f"{value:.2f}"


def _text(value: str) -> str:
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def revenue_csv(report: RevenueReportOut, branch_label: str, delimiter: str = "comma") -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=DELIMITERS[delimiter], lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADERS)
    label = _text(branch_label)
    for p in report.points:
        writer.writerow([
            label, f"{GRANULARITY_LABEL[report.granularity]} {p.period}", p.period_start.isoformat(), p.period_end.isoformat(),
            _money(p.revenue), _money(p.sales_revenue), _money(p.preorder_revenue),
            p.order_count, p.sales_count, p.preorder_count,
        ])
    t = report.totals
    writer.writerow([
        label, "Tổng cộng", report.date_from.isoformat(), report.date_to.isoformat(),
        _money(t.revenue), _money(t.sales_revenue), _money(t.preorder_revenue),
        t.order_count, sum(p.sales_count for p in report.points), sum(p.preorder_count for p in report.points),
    ])
    return "﻿".encode() + out.getvalue().encode("utf-8")  # BOM first


def export_filename(granularity: str, date_from: date, date_to: date, branch_code: str | None) -> str:
    """ASCII only (safe in every browser): doanh-thu_day_2026-11-01_2026-11-30_CN01.csv"""
    scope = "".join(c for c in (branch_code or "toan-chuoi") if c.isalnum() or c in "-_") or "chi-nhanh"
    return f"doanh-thu_{granularity}_{date_from.isoformat()}_{date_to.isoformat()}_{scope}.csv"

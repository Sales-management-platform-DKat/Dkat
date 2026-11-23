"""Response schemas for /reports (JSON uses camelCase)."""
from datetime import date
from typing import Literal

from app.modules.auth.schemas import CamelModel

Granularity = Literal["day", "week", "month", "year"]


class RevenuePoint(CamelModel):
    period: str  # day 2026-11-24 | week 2026-W48 (ISO, Monday start) | month 2026-11 | year 2026
    period_start: date  # first day of the period (Vietnam time)
    period_end: date  # last day of the period; data is still limited to [from, to]
    revenue: float  # sales_revenue + preorder_revenue
    sales_revenue: float
    preorder_revenue: float
    order_count: int
    sales_count: int
    preorder_count: int


class RevenueTotals(CamelModel):
    revenue: float
    sales_revenue: float
    preorder_revenue: float
    order_count: int


class RevenueReportOut(CamelModel):
    granularity: Granularity
    date_from: date
    date_to: date
    branch_id: int | None  # None = every branch of the store (OWNER only)
    timezone: str
    totals: RevenueTotals
    points: list[RevenuePoint]  # one per period from `from` to `to`, 0 when nothing was sold

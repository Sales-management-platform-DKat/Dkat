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


# ---- dashboard (FR-06.5) ---------------------------------------------------------------------------

TopProductSort = Literal["revenue", "quantity"]


class PeriodRef(CamelModel):
    date_from: date
    date_to: date


class SummaryMetric(CamelModel):
    value: float
    previous: float  # same metric over the previous period (same number of days, just before `from`)
    change_percent: float | None  # (value - previous) / previous * 100, 1 decimal; null when previous = 0


class CountMetric(CamelModel):
    value: int
    previous: int
    change_percent: float | None


class RevenueSummaryOut(CamelModel):
    date_from: date
    date_to: date
    branch_id: int | None
    previous_period: PeriodRef
    revenue: SummaryMetric
    order_count: CountMetric
    average_order_value: SummaryMetric  # revenue / order_count (0 when there is no order)
    sales_revenue: float  # split of `revenue.value`
    preorder_revenue: float


class TopProductOut(CamelModel):
    rank: int
    sku: str
    product_name: str  # snapshot name of the most recent sale of this SKU in the period
    quantity: int
    revenue: float  # sum of line totals (before order-level discounts)


class TopProductsOut(CamelModel):
    date_from: date
    date_to: date
    branch_id: int | None
    sort_by: TopProductSort
    limit: int
    items: list[TopProductOut]

"""Revenue report for charts (FR-06.1 - FR-06.4, FR-06.6) and dashboard cards / top products (FR-06.5).

- Periods are Vietnam-time calendar periods (UTC+7); weeks start on Monday (ISO weeks).
- `from` / `to` are Vietnam dates, both included. Every period between them is returned, with 0 when
  nothing was sold, so the chart line has no gaps. The first/last period may be partial.
- Scope: OWNER the whole store or one branch; MANAGER must pass one of their branches (checked by
  require_branch_access in the router); EMPLOYEE is rejected in the router.
"""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import CurrentUser
from app.modules.reports import repository
from app.modules.reports.schemas import (
    CountMetric,
    PeriodRef,
    RevenuePoint,
    RevenueReportOut,
    RevenueSummaryOut,
    RevenueTotals,
    SummaryMetric,
    TopProductOut,
    TopProductsOut,
)

VN_TZ = timezone(timedelta(hours=repository.VN_OFFSET_HOURS))
MAX_POINTS = 400  # e.g. 13 months of days; protects the server and the chart


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


def period_start(d: date, granularity: str) -> date:
    if granularity == "day":
        return d
    if granularity == "week":
        return d - timedelta(days=d.weekday())  # Monday
    if granularity == "month":
        return d.replace(day=1)
    return d.replace(month=1, day=1)


def next_period(start: date, granularity: str) -> date:
    if granularity == "day":
        return start + timedelta(days=1)
    if granularity == "week":
        return start + timedelta(days=7)
    if granularity == "month":
        return date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return date(start.year + 1, 1, 1)


def period_label(start: date, granularity: str) -> str:
    if granularity == "day":
        return start.isoformat()
    if granularity == "week":
        year, week, _ = start.isocalendar()
        return f"{year}-W{week:02d}"
    if granularity == "month":
        return f"{start.year}-{start.month:02d}"
    return str(start.year)


def default_from(to: date, granularity: str) -> date:
    """Default window: 30 days / 12 weeks / 12 months / 5 years ending at `to`."""
    if granularity == "day":
        return to - timedelta(days=29)
    if granularity == "week":
        return period_start(to, "week") - timedelta(weeks=11)
    if granularity == "month":
        months = to.year * 12 + to.month - 1 - 11
        return date(months // 12, months % 12 + 1, 1)
    return date(to.year - 4, 1, 1)


def vn_day_start_utc(d: date) -> datetime:
    """00:00 Vietnam time of `d`, as a naive UTC datetime (how paid_at / fulfilled_at are stored)."""
    return datetime.combine(d, time.min) - timedelta(hours=repository.VN_OFFSET_HOURS)


def _check_scope_and_dates(
    actor: CurrentUser, branch_id: int | None, date_from: date | None, date_to: date | None, default_from_fn
) -> tuple[date, date]:
    """Rules shared by every report. The router already rejected EMPLOYEE (403) and a branchId outside
    the user's branches (403); here a MANAGER must still name a branch, and the dates must be valid."""
    if branch_id is None and not actor.is_owner:
        raise AppError.bad_request("Quản lý phải chọn chi nhánh (branchId) thuộc phân công")
    date_to = date_to or today_vn()
    date_from = date_from or default_from_fn(date_to)
    if date_from > date_to:
        raise AppError.validation(
            "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc",
            [{"field": "from", "message": "from must be <= to", "type": "date_range"}],
        )
    return date_from, date_to


def _utc_window(date_from: date, date_to: date) -> dict:
    return {"start_utc": vn_day_start_utc(date_from), "end_utc": vn_day_start_utc(date_to + timedelta(days=1))}


def _default_30_days(to: date) -> date:
    return to - timedelta(days=29)


def _metric(value: float, previous: float) -> SummaryMetric:
    change = None if previous == 0 else round((value - previous) / previous * 100, 1)
    return SummaryMetric(value=round(value, 2), previous=round(previous, 2), change_percent=change)


async def _totals(db: AsyncSession, store_id: int, date_from: date, date_to: date, branch_id: int | None) -> dict:
    days = await repository.daily_revenue(db, store_id, branch_id=branch_id, **_utc_window(date_from, date_to))
    sales = sum(d["sales"] for d in days.values())
    preorders = sum(d["preorders"] for d in days.values())
    count = sum(d["sales_count"] + d["preorder_count"] for d in days.values())
    return {"sales": sales, "preorders": preorders, "revenue": sales + preorders, "count": count}


async def summary(
    db: AsyncSession, actor: CurrentUser, *, date_from: date | None, date_to: date | None, branch_id: int | None
) -> RevenueSummaryOut:
    """Dashboard cards: revenue, order count, average order value, % change vs the previous period
    (same number of days, ending the day before `from`). Default period: the last 30 days."""
    date_from, date_to = _check_scope_and_dates(actor, branch_id, date_from, date_to, _default_30_days)
    length = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=length - 1)

    cur = await _totals(db, actor.store_id, date_from, date_to, branch_id)
    prev = await _totals(db, actor.store_id, prev_from, prev_to, branch_id)
    cur_aov = cur["revenue"] / cur["count"] if cur["count"] else 0.0
    prev_aov = prev["revenue"] / prev["count"] if prev["count"] else 0.0
    return RevenueSummaryOut(
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
        previous_period=PeriodRef(date_from=prev_from, date_to=prev_to),
        revenue=_metric(cur["revenue"], prev["revenue"]),
        order_count=CountMetric(
            value=cur["count"], previous=prev["count"], change_percent=_metric(cur["count"], prev["count"]).change_percent
        ),
        average_order_value=_metric(cur_aov, prev_aov),
        sales_revenue=round(cur["sales"], 2),
        preorder_revenue=round(cur["preorders"], 2),
    )


async def top_products(
    db: AsyncSession,
    actor: CurrentUser,
    *,
    date_from: date | None,
    date_to: date | None,
    branch_id: int | None,
    limit: int,
    sort_by: str,
) -> TopProductsOut:
    """Best sellers by SKU over the orders that count as revenue. Default period: the last 30 days."""
    date_from, date_to = _check_scope_and_dates(actor, branch_id, date_from, date_to, _default_30_days)
    rows = await repository.product_lines(db, actor.store_id, branch_id=branch_id, **_utc_window(date_from, date_to))

    by_sku: dict[str, dict] = {}
    for r in rows:  # one row per (sku, name snapshot): merge names, keep the newest one
        item = by_sku.setdefault(r["sku"], {"sku": r["sku"], "name": r["name"], "quantity": 0, "revenue": 0.0, "last_at": r["last_at"]})
        item["quantity"] += int(r["quantity"])
        item["revenue"] += float(r["revenue"])
        if r["last_at"] > item["last_at"]:
            item["name"], item["last_at"] = r["name"], r["last_at"]

    primary = "revenue" if sort_by == "revenue" else "quantity"
    secondary = "quantity" if sort_by == "revenue" else "revenue"
    ranked = sorted(by_sku.values(), key=lambda i: (-i[primary], -i[secondary], i["sku"]))[:limit]
    return TopProductsOut(
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
        sort_by=sort_by,
        limit=limit,
        items=[
            TopProductOut(rank=n, sku=i["sku"], product_name=i["name"], quantity=i["quantity"], revenue=round(i["revenue"], 2))
            for n, i in enumerate(ranked, start=1)
        ],
    )


async def revenue_report(
    db: AsyncSession,
    actor: CurrentUser,
    *,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
    branch_id: int | None,
) -> RevenueReportOut:
    date_from, date_to = _check_scope_and_dates(
        actor, branch_id, date_from, date_to, lambda to: default_from(to, granularity)
    )

    starts = []
    start = period_start(date_from, granularity)
    while start <= date_to:
        starts.append(start)
        if len(starts) > MAX_POINTS:
            raise AppError.validation(
                f"Khoảng thời gian quá dài: tối đa {MAX_POINTS} kỳ, hãy chọn đơn vị lớn hơn",
                [{"field": "granularity", "message": f"At most {MAX_POINTS} periods", "type": "too_many_periods"}],
            )
        start = next_period(start, granularity)

    days = await repository.daily_revenue(
        db,
        actor.store_id,
        start_utc=vn_day_start_utc(date_from),
        end_utc=vn_day_start_utc(date_to + timedelta(days=1)),
        branch_id=branch_id,
    )

    buckets = {s: {"sales": 0.0, "sales_count": 0, "preorders": 0.0, "preorder_count": 0} for s in starts}
    for day, values in days.items():
        bucket = buckets[period_start(day, granularity)]
        for key, value in values.items():
            bucket[key] += value

    points = []
    for s in starts:
        b = buckets[s]
        points.append(
            RevenuePoint(
                period=period_label(s, granularity),
                period_start=s,
                period_end=next_period(s, granularity) - timedelta(days=1),
                revenue=round(b["sales"] + b["preorders"], 2),
                sales_revenue=round(b["sales"], 2),
                preorder_revenue=round(b["preorders"], 2),
                order_count=b["sales_count"] + b["preorder_count"],
                sales_count=b["sales_count"],
                preorder_count=b["preorder_count"],
            )
        )
    sales = round(sum(p.sales_revenue for p in points), 2)
    preorders = round(sum(p.preorder_revenue for p in points), 2)
    return RevenueReportOut(
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
        timezone="UTC+07:00 (Asia/Ho_Chi_Minh)",
        totals=RevenueTotals(
            revenue=round(sales + preorders, 2),
            sales_revenue=sales,
            preorder_revenue=preorders,
            order_count=sum(p.order_count for p in points),
        ),
        points=points,
    )

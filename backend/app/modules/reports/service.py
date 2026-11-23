"""Revenue report for charts (FR-06.1 - FR-06.4, FR-06.6).

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
from app.modules.reports.schemas import RevenuePoint, RevenueReportOut, RevenueTotals

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


async def revenue_report(
    db: AsyncSession,
    actor: CurrentUser,
    *,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
    branch_id: int | None,
) -> RevenueReportOut:
    if branch_id is None and not actor.is_owner:
        raise AppError.bad_request("Quản lý phải chọn chi nhánh (branchId) thuộc phân công")
    date_to = date_to or today_vn()
    date_from = date_from or default_from(date_to, granularity)
    if date_from > date_to:
        raise AppError.validation(
            "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc",
            [{"field": "from", "message": "from must be <= to", "type": "date_range"}],
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

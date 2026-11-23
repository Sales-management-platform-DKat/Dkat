"""Reports API.

GET /reports/revenue?granularity=day|week|month|year&from&to&branchId   chart series
GET /reports/revenue/export?granularity&from&to&branchId&delimiter     same data as CSV (UTF-8 BOM, for Excel)
GET /reports/summary?from&to&branchId                                   dashboard cards (+ % vs previous period)
GET /reports/top-products?limit&sortBy&from&to&branchId                 best sellers by SKU
    OWNER: whole store (no branchId) or one branch; MANAGER: branchId required and must be assigned
    (other -> 403, missing -> 400); EMPLOYEE: 403.
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_MANAGER, ROLE_OWNER, CurrentUser, require_branch_access, require_role
from app.db.session import get_db
from app.modules.reports import repository, service
from app.modules.reports.export import export_filename, revenue_csv
from app.modules.reports.schemas import (
    Granularity,
    RevenueReportOut,
    RevenueSummaryOut,
    TopProductSort,
    TopProductsOut,
)
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/reports", tags=["reports"])


# Same rules for every report: EMPLOYEE -> 403 before anything else; then require_branch_access
# (branchId outside the user's branches -> 403); MANAGER without branchId -> 400 in the service.
_report_roles = [Depends(require_role(ROLE_OWNER, ROLE_MANAGER))]


@router.get(
    "/revenue",
    dependencies=_report_roles,
    response_model=SuccessResponse[RevenueReportOut],
    response_model_by_alias=True,
)
async def revenue(
    granularity: Granularity = Query(default="day"),
    date_from: date | None = Query(default=None, alias="from", description="YYYY-MM-DD giờ VN (mặc định theo granularity)"),
    date_to: date | None = Query(default=None, alias="to", description="YYYY-MM-DD giờ VN, tính hết ngày (mặc định hôm nay)"),
    branch_id: int | None = Query(default=None, alias="branchId", gt=0),
    user: CurrentUser = Depends(require_branch_access()),  # branchId outside the user's scope -> 403
    db: AsyncSession = Depends(get_db),
):
    """Doanh thu theo kỳ (giờ Việt Nam, tuần bắt đầu thứ Hai), kỳ không có đơn = 0.
    Doanh thu = đơn bán PAID (theo paid_at) + đơn đặt trước FULFILLED chưa hoàn tiền (theo fulfilled_at)."""
    return ok(
        await service.revenue_report(
            db, user, granularity=granularity, date_from=date_from, date_to=date_to, branch_id=branch_id
        )
    )


@router.get(
    "/revenue/export",
    dependencies=_report_roles,
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV UTF-8 (BOM)"}},
)
async def revenue_export(
    granularity: Granularity = Query(default="day"),
    date_from: date | None = Query(default=None, alias="from", description="YYYY-MM-DD giờ VN"),
    date_to: date | None = Query(default=None, alias="to", description="YYYY-MM-DD giờ VN, tính hết ngày"),
    branch_id: int | None = Query(default=None, alias="branchId", gt=0),
    delimiter: Literal["comma", "semicolon"] = Query(
        default="comma", description="semicolon nếu Excel của máy dùng dấu ; làm dấu phân cách danh sách"
    ),
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Tải báo cáo doanh thu dạng CSV (UTF-8 có BOM, mở bằng Excel không lỗi tiếng Việt).
    Cùng số liệu, tham số và phân quyền với GET /reports/revenue; thêm dòng Tổng cộng."""
    report = await service.revenue_report(
        db, user, granularity=granularity, date_from=date_from, date_to=date_to, branch_id=branch_id
    )
    label, code = ("Toàn chuỗi", None)
    if branch_id is not None:
        label, code = await repository.branch_label(db, branch_id) or (f"Chi nhánh {branch_id}", str(branch_id))
    filename = export_filename(granularity, report.date_from, report.date_to, code)
    return Response(
        content=revenue_csv(report, label, delimiter),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.get(
    "/summary",
    dependencies=_report_roles,
    response_model=SuccessResponse[RevenueSummaryOut],
    response_model_by_alias=True,
)
async def summary(
    date_from: date | None = Query(default=None, alias="from", description="YYYY-MM-DD giờ VN (mặc định 30 ngày)"),
    date_to: date | None = Query(default=None, alias="to", description="YYYY-MM-DD giờ VN (mặc định hôm nay)"),
    branch_id: int | None = Query(default=None, alias="branchId", gt=0),
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Thẻ số dashboard: doanh thu, số đơn, giá trị trung bình/đơn và % thay đổi so với kỳ trước
    (cùng số ngày, liền trước `from`; null khi kỳ trước = 0)."""
    return ok(await service.summary(db, user, date_from=date_from, date_to=date_to, branch_id=branch_id))


@router.get(
    "/top-products",
    dependencies=_report_roles,
    response_model=SuccessResponse[TopProductsOut],
    response_model_by_alias=True,
)
async def top_products(
    limit: int = Query(default=10, ge=1, le=50),
    sort_by: TopProductSort = Query(default="revenue", alias="sortBy"),
    date_from: date | None = Query(default=None, alias="from", description="YYYY-MM-DD giờ VN (mặc định 30 ngày)"),
    date_to: date | None = Query(default=None, alias="to", description="YYYY-MM-DD giờ VN (mặc định hôm nay)"),
    branch_id: int | None = Query(default=None, alias="branchId", gt=0),
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Top sản phẩm theo SKU: tên (snapshot mới nhất), tổng số lượng, doanh thu dòng hàng.
    Cùng quy tắc tính doanh thu với /reports/revenue."""
    return ok(
        await service.top_products(
            db, user, date_from=date_from, date_to=date_to, branch_id=branch_id, limit=limit, sort_by=sort_by
        )
    )

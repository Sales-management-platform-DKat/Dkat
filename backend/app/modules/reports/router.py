"""Reports API.

GET /reports/revenue?granularity=day|week|month|year&from&to&branchId
    OWNER: whole store (no branchId) or one branch; MANAGER: branchId required and must be assigned
    (other -> 403, missing -> 400); EMPLOYEE: 403.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_MANAGER, ROLE_OWNER, CurrentUser, require_branch_access, require_role
from app.db.session import get_db
from app.modules.reports import service
from app.modules.reports.schemas import Granularity, RevenueReportOut
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/revenue",
    dependencies=[Depends(require_role(ROLE_OWNER, ROLE_MANAGER))],  # EMPLOYEE -> 403 before anything else
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

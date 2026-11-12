"""Branch management API (FR-02).

GET    /branches                 all roles  (OWNER: whole store, others: assigned branches)
GET    /branches/{id}            all roles  (403 when the branch is outside the user's scope)
POST   /branches                 OWNER      (201; creates inventory rows = 0)
PUT    /branches/{id}            OWNER
PATCH  /branches/{id}/status     OWNER      (409 BRANCH_HAS_OPEN_PREORDERS)
There is no DELETE: a branch is deactivated, never removed.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_OWNER, CurrentUser, require_auth, require_branch_access, require_role
from app.db.session import get_db
from app.modules.branches import service
from app.modules.branches.schemas import BranchCreatedOut, BranchIn, BranchOut, BranchStatus, BranchStatusIn
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/branches", tags=["branches"])

# Route-level dependencies run before the ones in the signature: role first, then branch scope
_owner_only = [Depends(require_role(ROLE_OWNER))]


@router.get("", response_model=SuccessResponse[list[BranchOut]], response_model_by_alias=True)
async def list_branches(
    status: BranchStatus | None = Query(default=None),
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Danh sách chi nhánh. `?status=ACTIVE|INACTIVE` để lọc."""
    return ok(await service.list_branches(db, user, status))


@router.get("/{branch_id}", response_model=SuccessResponse[BranchOut], response_model_by_alias=True)
async def get_branch(
    branch_id: int,
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Chi tiết chi nhánh. MANAGER/EMPLOYEE xem chi nhánh không được phân công -> 403."""
    return ok(await service.get_branch(db, user, branch_id))


@router.post(
    "",
    status_code=201,
    dependencies=_owner_only,
    response_model=SuccessResponse[BranchCreatedOut],
    response_model_by_alias=True,
)
async def create_branch(body: BranchIn, user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """Tạo chi nhánh (OWNER). Bắt buộc branchCode, name, address. 409 DUPLICATE_BRANCH_CODE nếu trùng mã."""
    return ok(await service.create_branch(db, user, body))


@router.put("/{branch_id}", dependencies=_owner_only, response_model=SuccessResponse[BranchOut], response_model_by_alias=True)
async def update_branch(
    branch_id: int,
    body: BranchIn,
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật mã, tên, địa chỉ, SĐT (OWNER). Trạng thái đổi qua PATCH /status."""
    return ok(await service.update_branch(db, user, branch_id, body))


@router.patch(
    "/{branch_id}/status", dependencies=_owner_only, response_model=SuccessResponse[BranchOut], response_model_by_alias=True
)
async def change_branch_status(
    branch_id: int,
    body: BranchStatusIn,
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """ACTIVE/INACTIVE (OWNER). 409 BRANCH_HAS_OPEN_PREORDERS khi còn đơn WAITING_STOCK/READY/NOTIFIED."""
    return ok(await service.change_status(db, user, branch_id, body.status))

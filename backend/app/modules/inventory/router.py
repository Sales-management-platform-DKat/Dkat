from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import CurrentUser, require_branch_access
from app.db.session import get_db
from app.modules.inventory import service
from app.modules.inventory.schemas import InventoryListOut
from app.utils.response import SuccessResponse, ok

router = APIRouter(tags=["inventory"])


@router.get(
    "/branches/{branch_id}/inventory",
    response_model=SuccessResponse[InventoryListOut],
    response_model_by_alias=True,
)
async def list_branch_inventory(
    branch_id: int,
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Tồn kho của 1 chi nhánh. OWNER: mọi chi nhánh; MANAGER/EMPLOYEE: chỉ chi nhánh được phân công, khác -> 403."""
    return ok(await service.list_inventory(db, user, branch_id))


@router.get("/inventory", response_model=SuccessResponse[InventoryListOut], response_model_by_alias=True)
async def list_inventory(
    branch_id: int | None = Query(default=None, gt=0),
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """Tồn kho các chi nhánh user được xem (lọc bằng get_accessible_branch_ids).
    `?branch_id=` để lọc 1 chi nhánh: chi nhánh ngoài phạm vi -> 403."""
    return ok(await service.list_inventory(db, user, branch_id))

"""Inventory business logic."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import CurrentUser, get_accessible_branch_ids
from app.modules.inventory import repository
from app.modules.inventory.schemas import InventoryItemOut, InventoryListOut


async def list_inventory(db: AsyncSession, user: CurrentUser, branch_id: int | None) -> InventoryListOut:
    """branch_id has already been checked by require_branch_access when given.
    Without it, the result is limited to the branches the user may see."""
    branch_ids = [branch_id] if branch_id is not None else get_accessible_branch_ids(user)
    rows = await repository.list_by_branches(db, branch_ids)
    return InventoryListOut(branch_ids=branch_ids, items=[InventoryItemOut(**r) for r in rows])

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.permissions import Actor, get_accessible_branch_ids, require_auth, require_branch_access
from app.db.session import get_db
from app.modules.inventory.schemas import InventoryId, InventoryItem
from app.modules.inventory.service import list_inventory

router = APIRouter(prefix="/inventory", tags=["inventory"])
Reader = Annotated[Actor, Depends(require_auth)]
Database = Annotated[Session, Depends(get_db)]


@router.get("")
def get_inventory(
    actor: Reader,
    session: Database,
    branch_id: InventoryId | None = Query(default=None, alias="branchId"),
    keyword: str | None = Query(default=None, max_length=200),
    low_stock: bool = Query(default=False, alias="lowStock"),
    page: int = Query(default=1, ge=1, le=21474836),
    size: int = Query(default=50, ge=1, le=100),
) -> list[InventoryItem]:
    try:
        db = session.connection()
        if branch_id is None:
            branches = get_accessible_branch_ids(db, actor)
        else:
            require_branch_access(db, actor, branch_id)
            branches = [branch_id]
        return list_inventory(
            db, actor.store_id, branches, keyword=keyword, low_stock=low_stock,
            limit=size, offset=(page - 1) * size,
        )
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.get("/{branch_id}/{variant_id}")
def get_inventory_item(
    branch_id: InventoryId, variant_id: InventoryId, actor: Reader, session: Database
) -> InventoryItem:
    try:
        db = session.connection()
        require_branch_access(db, actor, branch_id)
        rows = list_inventory(db, actor.store_id, [branch_id], variant_id=variant_id, limit=1)
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    if not rows:
        raise HTTPException(404, "Inventory item not found")
    return rows[0]

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.permissions import Actor, require_auth, require_owner
from app.modules.products import category_service
from app.modules.products.catalog_transaction import catalog_transaction as category_transaction
from app.modules.products.category_schemas import (
    Category, CategoryId, CategoryInput, CategoryNode, CategoryStatus, CategoryStatusInput,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def get_categories(
    actor: Annotated[Actor, Depends(require_auth)], status: CategoryStatus | None = None
) -> list[CategoryNode]:
    with category_transaction() as db:
        return category_service.list_categories(db, actor.store_id, status)


@router.post("", status_code=201)
def create_category(data: CategoryInput, actor: Annotated[Actor, Depends(require_owner)]) -> Category:
    with category_transaction() as db:
        return category_service.save_category(db, actor.store_id, data)


@router.put("/{category_id}")
def update_category(
    category_id: CategoryId, data: CategoryInput, actor: Annotated[Actor, Depends(require_owner)]
) -> Category:
    with category_transaction() as db:
        return category_service.save_category(db, actor.store_id, data, category_id)


@router.patch("/{category_id}/status")
def update_category_status(
    category_id: CategoryId, data: CategoryStatusInput, actor: Annotated[Actor, Depends(require_owner)]
) -> Category:
    with category_transaction() as db:
        return category_service.change_status(db, actor.store_id, category_id, data.status)

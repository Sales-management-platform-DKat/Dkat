from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.permissions import Actor, require_auth, require_owner
from app.modules.products import service, variant_service
from app.modules.products.catalog_transaction import catalog_transaction
from app.modules.products.schemas import (
    Product, ProductCreate, ProductDetail, ProductId, ProductInput, ProductRecord,
    ProductSort, ProductStatus, ProductStatusInput, VariantDetail,
)
from app.modules.products.variant_schemas import AttributeInput, AttributeRecord, VariantInput

router = APIRouter(tags=["products"])
Owner = Annotated[Actor, Depends(require_owner)]
Reader = Annotated[Actor, Depends(require_auth)]


@router.get("/products", response_model=list[Product])
def get_products(
    actor: Reader,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=2147483647),
    keyword: str | None = Query(default=None, max_length=200),
    category_id: ProductId | None = Query(default=None, alias="categoryId"),
    status: ProductStatus = "ACTIVE",
    page: int | None = Query(default=None, ge=1, le=21474836),
    size: int | None = Query(default=None, ge=1, le=100),
    sort: ProductSort = "id",
) -> list[Product]:
    if page is not None or size is not None:
        limit = size or 50
        offset = ((page or 1) - 1) * limit
    with catalog_transaction() as db:
        return service.list_products(
            db, actor.store_id, limit, offset,
            keyword=keyword, category_id=category_id, status=status, sort=sort,
        )


@router.get("/products/{product_id}")
def get_product(product_id: ProductId, actor: Reader) -> ProductDetail:
    with catalog_transaction() as db:
        return service.get_product_detail(db, actor.store_id, product_id)


@router.post("/products", status_code=201)
def create_product(data: ProductCreate, actor: Owner) -> ProductRecord:
    # Read the sequence after acquiring the store lock, even after waiting for another writer.
    with catalog_transaction(read_committed=True) as db:
        return service.create_product(db, actor.store_id, actor.user_id, data)


@router.put("/products/{product_id}")
def update_product(product_id: ProductId, data: ProductInput, actor: Owner) -> ProductRecord:
    with catalog_transaction() as db:
        return service.update_product(db, actor.store_id, product_id, data)


@router.patch("/products/{product_id}/status")
def update_product_status(product_id: ProductId, data: ProductStatusInput, actor: Owner) -> ProductRecord:
    with catalog_transaction() as db:
        return service.change_product_status(db, actor.store_id, product_id, data.status)


@router.get("/attributes")
def get_attributes(actor: Reader) -> list[AttributeRecord]:
    with catalog_transaction() as db:
        return variant_service.list_attributes(db, actor.store_id)


@router.post("/attributes", status_code=201)
def create_attribute(data: AttributeInput, actor: Owner) -> AttributeRecord:
    with catalog_transaction() as db:
        return variant_service.create_attribute(db, actor.store_id, data)


@router.post("/products/{product_id}/variants", status_code=201)
def create_variant(product_id: ProductId, data: VariantInput, actor: Owner) -> VariantDetail:
    with catalog_transaction() as db:
        return variant_service.save_variant(db, actor.store_id, data, product_id=product_id)


@router.put("/variants/{variant_id}")
def update_variant(variant_id: ProductId, data: VariantInput, actor: Owner) -> VariantDetail:
    with catalog_transaction() as db:
        return variant_service.save_variant(db, actor.store_id, data, variant_id=variant_id)


@router.patch("/variants/{variant_id}/status")
def update_variant_status(variant_id: ProductId, data: ProductStatusInput, actor: Owner) -> VariantDetail:
    with catalog_transaction() as db:
        return variant_service.change_variant_status(db, actor.store_id, variant_id, data.status)

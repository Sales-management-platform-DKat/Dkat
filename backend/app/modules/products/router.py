from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.core.permissions import Actor, require_auth, require_owner
from app.modules.products import service, variant_service
from app.modules.products.catalog_transaction import catalog_transaction
from app.modules.products.csv_parser import MAX_FILE_BYTES
from app.modules.products.csv_schemas import CsvImportResult
from app.modules.products.csv_service import import_products
from app.modules.products.image_storage import MAX_PRODUCT_IMAGE_BYTES, product_image_path, save_product_image
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


@router.post("/products/import-csv", responses={201: {"model": CsvImportResult}})
def import_product_csv(
    actor: Owner, response: Response, file: Annotated[UploadFile, File()],
    dry_run: bool = Query(default=True, alias="dryRun"),
) -> CsvImportResult:
    try:
        content = file.file.read(MAX_FILE_BYTES + 1)
    finally:
        file.file.close()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, {"code": "CSV_FILE_TOO_LARGE", "maxBytes": MAX_FILE_BYTES})
    with catalog_transaction() as db:
        result = import_products(db, actor, content, dry_run)
    response.status_code = 200 if dry_run else 201
    return result


@router.post("/products/images", status_code=201)
def upload_product_image(actor: Owner, file: Annotated[UploadFile, File()]) -> dict:
    try:
        content = file.file.read(MAX_PRODUCT_IMAGE_BYTES + 1)
        filename, content_type = save_product_image(content, file.content_type)
    finally:
        file.file.close()
    return {
        "imageUrl": f"/products/images/{filename}",
        "contentType": content_type,
        "size": len(content),
    }


@router.get("/products/images/{filename}", include_in_schema=False)
def get_product_image(filename: str) -> FileResponse:
    path = product_image_path(filename)
    extension = path.suffix.lower()
    media_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[extension]
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/products/images/{filename}", status_code=204, include_in_schema=False)
def delete_unused_product_image(filename: str, actor: Owner) -> Response:
    path = product_image_path(filename)
    image_url = f"/products/images/{filename}"
    with catalog_transaction() as db:
        referenced = db.execute(
            text("SELECT 1 FROM products WHERE image_url=:image_url LIMIT 1"),
            {"image_url": image_url},
        ).first()
        if referenced:
            raise HTTPException(409, "Ảnh đang được dùng bởi sản phẩm.")
        path.unlink(missing_ok=True)
    return Response(status_code=204)


@router.get("/products/{product_id}")
def get_product(product_id: ProductId, actor: Reader) -> ProductDetail:
    with catalog_transaction() as db:
        product = service.get_product_detail(db, actor.store_id, product_id)
    if actor.role != "OWNER":
        for variant in product.variants:
            variant.cost_price = None
    return product


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

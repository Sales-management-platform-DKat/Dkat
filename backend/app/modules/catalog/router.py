"""Public catalog API: no login (FR-07.1 - FR-07.3), rate limited per IP.

GET /public/products?keyword&categoryId&attr&inStock&page&size&storeId
GET /public/products/{id}         detail page + pre-order form (FR-07.4)
GET /public/branches?storeId      ACTIVE branches
GET /public/categories?storeId
"""
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter, rate_limit
from app.db.session import get_db
from app.modules.catalog import service
from app.modules.catalog.schemas import PublicBranchOut, PublicCategoryNode, PublicProductDetailOut, PublicProductPageOut
from app.utils.response import SuccessResponse, ok

# One budget per IP shared by every /public route (e.g. 60 requests / minute)
public_limiter = SlidingWindowLimiter(limit=settings.PUBLIC_RATE_LIMIT_PER_MINUTE, window_seconds=60)

router = APIRouter(prefix="/public", tags=["public"], dependencies=[Depends(rate_limit(public_limiter))])

MAX_PAGE_SIZE = 50


@router.get("/products", response_model=SuccessResponse[PublicProductPageOut], response_model_by_alias=True)
async def search_products(
    keyword: str | None = Query(default=None, max_length=100),
    category_id: int | None = Query(default=None, alias="categoryId", gt=0),
    attr: list[str] = Query(default=[], description="Lặp lại được: attr=Màu:Đỏ&attr=Size:M"),
    in_stock: bool | None = Query(default=None, alias="inStock"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    store_id: int | None = Query(default=None, alias="storeId", gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Tra cứu sản phẩm ACTIVE. categoryId gồm cả danh mục con. attr: biến thể phải có đủ mọi giá trị.
    inStock=true: còn hàng khả dụng ở ít nhất một chi nhánh; false: hết hàng."""
    attrs = service.parse_attr_filters(attr)
    return ok(
        await service.search_products(
            db,
            store_id=store_id,
            keyword=keyword,
            category_id=category_id,
            attrs=attrs,
            in_stock=in_stock,
            page=page,
            size=size,
        )
    )


@router.get("/products/{product_id}", response_model=SuccessResponse[PublicProductDetailOut], response_model_by_alias=True)
async def product_detail(product_id: int = Path(gt=0), db: AsyncSession = Depends(get_db)):
    """Trang chi tiết + form đặt trước: mô tả, biến thể (id, sku, tên, thuộc tính, giá) và với mỗi
    chi nhánh ACTIVE: IN_STOCK / OUT_OF_STOCK (không có số lượng). Sản phẩm ẩn / không tồn tại -> 404."""
    return ok(await service.product_detail(db, product_id))


@router.get("/branches", response_model=SuccessResponse[list[PublicBranchOut]], response_model_by_alias=True)
async def list_branches(
    store_id: int | None = Query(default=None, alias="storeId", gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Chi nhánh ACTIVE: id, tên, địa chỉ, SĐT."""
    return ok(await service.list_branches(db, store_id))


@router.get("/categories", response_model=SuccessResponse[list[PublicCategoryNode]], response_model_by_alias=True)
async def category_tree(
    store_id: int | None = Query(default=None, alias="storeId", gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Cây danh mục ACTIVE (danh mục con của danh mục ngừng hoạt động bị ẩn)."""
    return ok(await service.category_tree(db, store_id))

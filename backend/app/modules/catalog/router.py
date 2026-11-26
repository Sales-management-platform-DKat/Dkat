"""Public catalog for the customer website (FR-07). No login; PUBLIC_RATE_LIMIT_PER_MINUTE requests / minute / IP
shared by every route below (default 60).

GET /public/products?keyword&categoryId&attr&inStock&page&size&storeId   search (FR-07.1 - 07.3)
GET /public/products/{id}                                                 detail + pre-order form (FR-07.4)
GET /public/categories?storeId                                            tree of ACTIVE categories
GET /public/branches?storeId                                              ACTIVE branches
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter, rate_limit
from app.db.session import engine
from app.modules.catalog import service
from app.modules.catalog.schemas import PublicBranch, PublicCategoryNode, PublicProductDetail, PublicProductPage

public_limiter = SlidingWindowLimiter(limit=settings.PUBLIC_RATE_LIMIT_PER_MINUTE, window_seconds=60)
router = APIRouter(prefix="/public", tags=["public-catalog"], dependencies=[Depends(rate_limit(public_limiter))])

Id = Annotated[int, Path(gt=0, le=9223372036854775807)]
StoreId = Annotated[int | None, Query(alias="storeId", gt=0, le=9223372036854775807,
                                      description="Bắt buộc khi hệ thống có nhiều cửa hàng")]
MAX_PAGE_SIZE = 50


def run(fn, *args, **kwargs):
    try:
        with engine.connect() as db:
            return fn(db, *args, **kwargs)
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.get("/products")
def search_products(
    store_id: StoreId = None,
    keyword: Annotated[str | None, Query(max_length=100, description="Tìm trong tên sản phẩm")] = None,
    category_id: Annotated[int | None, Query(alias="categoryId", gt=0, description="Gồm cả danh mục con")] = None,
    attr: Annotated[list[str], Query(description="Lặp lại được: attr=Màu:Đen&attr=Size:M (cùng một biến thể)")] = [],  # noqa: B006
    in_stock: Annotated[bool | None, Query(alias="inStock", description="true: còn hàng khả dụng ở ít nhất 1 chi nhánh; false: hết hàng")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> PublicProductPage:
    """Tra cứu sản phẩm ACTIVE có biến thể ACTIVE. Mỗi sản phẩm: id, tên, ảnh, danh mục, khoảng giá, inStock."""
    attrs = service.parse_attr_filters(attr)
    return run(service.search_products, store_id=store_id, keyword=keyword, category_id=category_id,
               attrs=attrs, in_stock=in_stock, page=page, size=size)


@router.get("/products/{product_id}")
def product_detail(product_id: Id) -> PublicProductDetail:
    """Chi tiết + form đặt trước: biến thể ACTIVE (id, SKU, tên, thuộc tính, giá) và với mỗi chi nhánh ACTIVE
    chỉ IN_STOCK / OUT_OF_STOCK. Sản phẩm ẩn hoặc không tồn tại -> 404."""
    return run(service.product_detail, product_id)


@router.get("/categories")
def categories(store_id: StoreId = None) -> list[PublicCategoryNode]:
    """Cây danh mục ACTIVE (danh mục INACTIVE ẩn cả nhánh con)."""
    return run(service.category_tree, store_id)


@router.get("/branches")
def branches(store_id: StoreId = None) -> list[PublicBranch]:
    return run(service.branches, store_id)

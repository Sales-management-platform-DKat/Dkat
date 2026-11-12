"""Product business logic."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import CurrentUser
from app.db.session import transaction
from app.modules.products import repository
from app.modules.products.models import Product
from app.modules.products.schemas import ProductCreateIn, ProductOut


def _to_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.product_id,
        store_id=p.store_id,
        category_id=p.category_id,
        product_code=p.product_code,
        name=p.name,
        description=p.description,
        image_url=p.image_url,
        status=p.status,
        created_at=p.created_at,
        created_by=p.created_by,
    )


async def create_product(db: AsyncSession, user: CurrentUser, body: ProductCreateIn) -> ProductOut:
    """Only reached by OWNER (checked in the router). The product always belongs to the caller's store."""
    category = await repository.get_category(db, user.store_id, body.category_id)
    if category is None or category.status != "ACTIVE":
        raise AppError.validation(
            "Danh mục không tồn tại hoặc đã ngừng hoạt động",
            [{"field": "categoryId", "message": "Category not found in this store", "type": "not_found"}],
        )
    async with transaction(db):
        product = await repository.insert_product(
            db,
            Product(
                store_id=user.store_id,
                category_id=body.category_id,
                product_code=body.product_code,
                name=body.name,
                description=body.description,
                image_url=body.image_url,
                created_by=user.id,
            ),
        )
    return _to_out(product)

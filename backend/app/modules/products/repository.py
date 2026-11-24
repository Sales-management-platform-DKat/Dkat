"""SQL queries for products."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models import Category, Product


async def get_category(db: AsyncSession, store_id: int, category_id: int) -> Category | None:
    stmt = select(Category).where(Category.category_id == category_id, Category.store_id == store_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def insert_product(db: AsyncSession, product: Product) -> Product:
    db.add(product)
    await db.flush()
    await db.refresh(product)  # load server defaults (created_at, status)
    return product

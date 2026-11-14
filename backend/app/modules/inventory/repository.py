"""SQL queries for inventory."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductVariant


async def list_by_branches(db: AsyncSession, branch_ids: list[int]) -> list[dict]:
    """Stock rows for the given branches. An empty list returns nothing (never "all branches")."""
    if not branch_ids:
        return []
    stmt = (
        select(
            Inventory.branch_id,
            Inventory.variant_id,
            ProductVariant.sku,
            ProductVariant.variant_name,
            Product.product_id,
            Product.name.label("product_name"),
            Inventory.quantity,
            Inventory.updated_at,
        )
        .join(ProductVariant, ProductVariant.variant_id == Inventory.variant_id)
        .join(Product, Product.product_id == ProductVariant.product_id)
        .where(Inventory.branch_id.in_(branch_ids))
        .order_by(Inventory.branch_id, Product.name, ProductVariant.sku)
    )
    return [dict(row._mapping) for row in await db.execute(stmt)]

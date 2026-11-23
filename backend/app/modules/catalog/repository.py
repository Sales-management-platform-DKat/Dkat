"""SQL for the public catalog. Read-only.

Available stock (same formula as the inventory module):
    inventory.quantity - SUM(preorder_items.allocated_quantity of WAITING_STOCK/READY/NOTIFIED
                             pre-orders at the same branch for the same variant)
Only ACTIVE branches and ACTIVE variants count.

Index use (checked with EXPLAIN, see scripts/check_public_catalog.py):
- variants of a product    -> product_variants.idx_variants_product_status (product_id, status)
- stock of a variant       -> inventory.idx_inventory_variant (variant_id) or uq_inventory_branch_variant
                              (branch_id, variant_id), branches PRIMARY
- reservations             -> preorder_items.idx_pi_variant_preorder (variant_id, preorder_id), preorders PRIMARY
- attribute filter         -> variant_attribute_values.uq_variant_attribute (variant_id, attribute_id)
- category / store filter  -> products.idx_products_store_cat_status / idx_products_category
keyword uses LIKE '%...%', which cannot use a B-tree index (products of one store are scanned).
"""
from sqlalchemy import and_, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.branches.models import Branch
from app.modules.inventory.models import Inventory
from app.modules.products.models import Attribute, Category, Product, ProductVariant, VariantAttributeValue

OPEN_PREORDER_STATUSES = ("WAITING_STOCK", "READY", "NOTIFIED")

# Lightweight table handles: the preorders module owns these tables, we only read two columns each
_preorders = table("preorders", column("preorder_id"), column("branch_id"), column("status"))
_preorder_items = table("preorder_items", column("preorder_id"), column("variant_id"), column("allocated_quantity"))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _reserved_for_inventory_row():
    """Correlated scalar: quantity held by open pre-orders for the enclosing inventory row's
    (branch, variant). Available stock = Inventory.quantity - this."""
    return (
        select(func.coalesce(func.sum(_preorder_items.c.allocated_quantity), 0))
        .select_from(_preorder_items.join(_preorders, _preorders.c.preorder_id == _preorder_items.c.preorder_id))
        .where(
            _preorder_items.c.variant_id == Inventory.variant_id,
            _preorders.c.branch_id == Inventory.branch_id,
            _preorders.c.status.in_(OPEN_PREORDER_STATUSES),
        )
        .scalar_subquery()
    )


def _has_available_stock(product_id_col):
    """EXISTS: an ACTIVE variant of the product has available stock > 0 at an ACTIVE branch."""
    variant = aliased(ProductVariant)
    return (
        select(Inventory.inventory_id)
        .join(variant, and_(variant.variant_id == Inventory.variant_id, variant.status == "ACTIVE"))
        .join(Branch, and_(Branch.branch_id == Inventory.branch_id, Branch.status == "ACTIVE"))
        .where(variant.product_id == product_id_col, Inventory.quantity > _reserved_for_inventory_row())
        .exists()
    )


def _available_pairs_stmt(variant_ids: list[int], branch_ids: list[int]):
    return select(Inventory.variant_id, Inventory.branch_id).where(
        Inventory.variant_id.in_(variant_ids),
        Inventory.branch_id.in_(branch_ids),
        Inventory.quantity > _reserved_for_inventory_row(),
    )


def _search_stmt(
    *,
    category_ids: list[int],
    store_id: int | None,
    keyword: str | None,
    attrs: list[tuple[str, str]],
    in_stock: bool | None,
):
    variant = aliased(ProductVariant)
    matching_variant = select(variant.variant_id).where(
        variant.product_id == Product.product_id, variant.status == "ACTIVE"
    )
    for name, value in attrs:  # the SAME variant must have every requested attribute value
        matching_variant = matching_variant.where(
            select(VariantAttributeValue.variant_attribute_value_id)
            .join(
                Attribute,
                and_(Attribute.attribute_id == VariantAttributeValue.attribute_id, Attribute.status == "ACTIVE"),
            )
            .where(
                VariantAttributeValue.variant_id == variant.variant_id,
                Attribute.name == name,
                VariantAttributeValue.value == value,
            )
            .exists()
        )

    stmt = select(Product.product_id).where(
        Product.status == "ACTIVE",
        Product.category_id.in_(category_ids),
        matching_variant.exists(),  # a product without ACTIVE variants has no price: never listed
    )
    if store_id is not None:
        stmt = stmt.where(Product.store_id == store_id)
    if keyword:
        stmt = stmt.where(Product.name.like(f"%{_escape_like(keyword)}%", escape="\\"))
    if in_stock is True:
        stmt = stmt.where(_has_available_stock(Product.product_id))
    elif in_stock is False:
        stmt = stmt.where(~_has_available_stock(Product.product_id))
    return stmt


async def search_product_ids(
    db: AsyncSession,
    *,
    category_ids: list[int],
    store_id: int | None,
    keyword: str | None,
    attrs: list[tuple[str, str]],
    in_stock: bool | None,
    page: int,
    size: int,
) -> tuple[list[int], int]:
    if not category_ids:
        return [], 0
    stmt = _search_stmt(category_ids=category_ids, store_id=store_id, keyword=keyword, attrs=attrs, in_stock=in_stock)
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    page_stmt = stmt.order_by(Product.name, Product.product_id).limit(size).offset((page - 1) * size)
    return list((await db.execute(page_stmt)).scalars()), total


async def product_cards(db: AsyncSession, product_ids: list[int]) -> dict[int, dict]:
    """Public fields for the given products: name, image, category, price range, in_stock flag."""
    if not product_ids:
        return {}
    base = (
        await db.execute(
            select(
                Product.product_id,
                Product.name,
                Product.image_url,
                Category.category_id,
                Category.name.label("category_name"),
            )
            .join(Category, Category.category_id == Product.category_id)
            .where(Product.product_id.in_(product_ids))
        )
    ).all()
    prices = {
        pid: (lo, hi)
        for pid, lo, hi in (
            await db.execute(
                select(ProductVariant.product_id, func.min(ProductVariant.price), func.max(ProductVariant.price))
                .where(ProductVariant.product_id.in_(product_ids), ProductVariant.status == "ACTIVE")
                .group_by(ProductVariant.product_id)
            )
        ).all()
    }
    in_stock = set(
        (
            await db.execute(
                select(Product.product_id).where(
                    Product.product_id.in_(product_ids), _has_available_stock(Product.product_id)
                )
            )
        ).scalars()
    )
    cards = {}
    for row in base:
        lo, hi = prices.get(row.product_id, (0, 0))
        cards[row.product_id] = {
            "id": row.product_id,
            "name": row.name,
            "image_url": row.image_url,
            "category": {"id": row.category_id, "name": row.category_name},
            "price_min": float(lo),
            "price_max": float(hi),
            "in_stock": row.product_id in in_stock,
        }
    return cards


async def get_product(db: AsyncSession, product_id: int):
    """The product row with its category, or None. Visibility is decided by the service."""
    return (
        await db.execute(
            select(
                Product.product_id,
                Product.store_id,
                Product.status,
                Product.name,
                Product.description,
                Product.image_url,
                Product.category_id,
                Category.name.label("category_name"),
            )
            .join(Category, Category.category_id == Product.category_id)
            .where(Product.product_id == product_id)
        )
    ).first()


async def active_variants(db: AsyncSession, product_id: int) -> list:
    stmt = (
        select(ProductVariant.variant_id, ProductVariant.sku, ProductVariant.variant_name, ProductVariant.price)
        .where(ProductVariant.product_id == product_id, ProductVariant.status == "ACTIVE")
        .order_by(ProductVariant.variant_id)
    )
    return list((await db.execute(stmt)).all())


async def variant_attributes(db: AsyncSession, variant_ids: list[int]) -> dict[int, list[tuple[str, str]]]:
    """ACTIVE attribute (name, value) pairs per variant, ordered by attribute name."""
    if not variant_ids:
        return {}
    stmt = (
        select(VariantAttributeValue.variant_id, Attribute.name, VariantAttributeValue.value)
        .join(Attribute, and_(Attribute.attribute_id == VariantAttributeValue.attribute_id, Attribute.status == "ACTIVE"))
        .where(VariantAttributeValue.variant_id.in_(variant_ids))
        .order_by(VariantAttributeValue.variant_id, Attribute.name)
    )
    result: dict[int, list[tuple[str, str]]] = {}
    for variant_id, name, value in (await db.execute(stmt)).all():
        result.setdefault(variant_id, []).append((name, value))
    return result


async def active_branches(db: AsyncSession, store_id: int | None) -> list[Branch]:
    stmt = select(Branch).where(Branch.status == "ACTIVE")
    if store_id is not None:
        stmt = stmt.where(Branch.store_id == store_id)
    return list((await db.execute(stmt.order_by(Branch.name, Branch.branch_id))).scalars())


async def available_pairs(db: AsyncSession, variant_ids: list[int], branch_ids: list[int]) -> set[tuple[int, int]]:
    """(variant_id, branch_id) pairs with available stock > 0. A missing inventory row = not available."""
    if not variant_ids or not branch_ids:
        return set()
    return {(v, b) for v, b in (await db.execute(_available_pairs_stmt(variant_ids, branch_ids))).all()}


async def list_categories(db: AsyncSession, store_id: int | None) -> list[Category]:
    stmt = select(Category)
    if store_id is not None:
        stmt = stmt.where(Category.store_id == store_id)
    return list((await db.execute(stmt.order_by(Category.name, Category.category_id))).scalars())


def explain_targets(
    store_id: int, category_ids: list[int], product_ids: list[int], variant_ids: list[int], branch_ids: list[int]
):
    """Statements whose plans scripts/check_public_catalog.py inspects with EXPLAIN.
    Pass ids that exist: MySQL returns no plan for an impossible WHERE."""
    return {
        "availability": _available_pairs_stmt(variant_ids, branch_ids),
        "search": _search_stmt(category_ids=category_ids, store_id=store_id, keyword=None, attrs=[("Size", "M")], in_stock=True),
        "price_range": select(ProductVariant.product_id, func.min(ProductVariant.price), func.max(ProductVariant.price))
        .where(ProductVariant.product_id.in_(product_ids), ProductVariant.status == "ACTIVE")
        .group_by(ProductVariant.product_id),
        "in_stock": select(Product.product_id).where(
            Product.product_id.in_(product_ids), _has_available_stock(Product.product_id)
        ),
    }

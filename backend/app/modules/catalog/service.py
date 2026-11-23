"""Public product search and category tree (FR-07.1 - FR-07.3). No login.

Visibility:
- a category is visible when it and all its ancestors are ACTIVE (a sub-tree under an INACTIVE
  category is hidden, together with its products);
- a product is listed when it is ACTIVE, its category is visible and it has >= 1 ACTIVE variant.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.catalog import repository
from app.modules.catalog.schemas import (
    PublicAttributeValue,
    PublicBranchAvailability,
    PublicBranchOut,
    PublicCategoryNode,
    PublicCategoryRef,
    PublicProductDetailOut,
    PublicProductOut,
    PublicProductPageOut,
    PublicVariantOut,
)
from app.modules.products.models import Category

MAX_ATTR_FILTERS = 5


def parse_attr_filters(raw: list[str]) -> list[tuple[str, str]]:
    """`attr=Màu:Đỏ&attr=Size:M` -> [("Màu", "Đỏ"), ("Size", "M")]. Name/value are case-insensitive."""
    if len(raw) > MAX_ATTR_FILTERS:
        raise AppError.validation(
            f"Tối đa {MAX_ATTR_FILTERS} bộ lọc thuộc tính",
            [{"field": "attr", "message": f"At most {MAX_ATTR_FILTERS} attr filters", "type": "too_many"}],
        )
    result = []
    for item in raw:
        name, sep, value = item.partition(":")
        name, value = name.strip(), value.strip()
        if not sep or not name or not value or len(name) > 100 or len(value) > 255:
            raise AppError.validation(
                "Bộ lọc thuộc tính phải có dạng tên:giá trị, ví dụ attr=Màu:Đỏ",
                [{"field": "attr", "message": f"Expected name:value, got {item!r}", "type": "format"}],
            )
        result.append((name, value))
    return result


def _visible_categories(categories: list[Category]) -> dict[int, Category]:
    by_id = {c.category_id: c for c in categories}
    visible: dict[int, bool] = {}

    def is_visible(cid: int, seen: frozenset[int] = frozenset()) -> bool:
        if cid in visible:
            return visible[cid]
        cat = by_id.get(cid)
        if cat is None or cat.status != "ACTIVE" or cid in seen:  # missing parent or a cycle -> hidden
            return False
        parent = cat.parent_category_id
        visible[cid] = parent is None or is_visible(parent, seen | {cid})
        return visible[cid]

    return {cid: c for cid, c in by_id.items() if is_visible(cid)}


def _children_map(visible: dict[int, Category]) -> dict[int | None, list[Category]]:
    # Keeps the DB order (ORDER BY name in the column's utf8mb4_unicode_ci collation: Vietnamese-aware,
    # "Áo" before "Quần"). Python's sort would compare code points and put "Áo" last.
    children: dict[int | None, list[Category]] = {}
    for c in visible.values():
        children.setdefault(c.parent_category_id, []).append(c)
    return children


def _with_descendants(root_id: int, children: dict[int | None, list[Category]]) -> list[int]:
    ids, stack = [], [root_id]
    while stack:
        cid = stack.pop()
        ids.append(cid)
        stack.extend(c.category_id for c in children.get(cid, []))
    return ids


async def category_tree(db: AsyncSession, store_id: int | None) -> list[PublicCategoryNode]:
    visible = _visible_categories(await repository.list_categories(db, store_id))
    children = _children_map(visible)

    def build(c: Category) -> PublicCategoryNode:
        return PublicCategoryNode(id=c.category_id, name=c.name, children=[build(x) for x in children.get(c.category_id, [])])

    return [build(c) for c in children.get(None, [])]


async def product_detail(db: AsyncSession, product_id: int) -> PublicProductDetailOut:
    """Detail page + pre-order form (FR-07.4). Hidden products answer 404 like unknown ids."""
    row = await repository.get_product(db, product_id)
    variants = await repository.active_variants(db, product_id) if row else []
    if (
        row is None
        or row.status != "ACTIVE"
        or row.category_id not in _visible_categories(await repository.list_categories(db, row.store_id))
        or not variants
    ):
        raise AppError.not_found("Không tìm thấy sản phẩm")

    variant_ids = [v.variant_id for v in variants]
    branch_ids = [b.branch_id for b in await repository.active_branches(db, row.store_id)]
    attributes = await repository.variant_attributes(db, variant_ids)
    available = await repository.available_pairs(db, variant_ids, branch_ids)
    prices = [float(v.price) for v in variants]
    return PublicProductDetailOut(
        id=row.product_id,
        name=row.name,
        description=row.description,
        image_url=row.image_url,
        category=PublicCategoryRef(id=row.category_id, name=row.category_name),
        price_min=min(prices),
        price_max=max(prices),
        in_stock=bool(available),  # same rule as inStock in the search results
        variants=[
            PublicVariantOut(
                id=v.variant_id,
                sku=v.sku,
                name=v.variant_name,
                price=float(v.price),
                attributes=[PublicAttributeValue(name=n, value=val) for n, val in attributes.get(v.variant_id, [])],
                branches=[
                    PublicBranchAvailability(
                        branch_id=b, availability="IN_STOCK" if (v.variant_id, b) in available else "OUT_OF_STOCK"
                    )
                    for b in branch_ids
                ],
            )
            for v in variants
        ],
    )


async def list_branches(db: AsyncSession, store_id: int | None) -> list[PublicBranchOut]:
    return [
        PublicBranchOut(id=b.branch_id, name=b.name, address=b.address, phone=b.phone)
        for b in await repository.active_branches(db, store_id)
    ]


async def search_products(
    db: AsyncSession,
    *,
    store_id: int | None,
    keyword: str | None,
    category_id: int | None,
    attrs: list[tuple[str, str]],
    in_stock: bool | None,
    page: int,
    size: int,
) -> PublicProductPageOut:
    visible = _visible_categories(await repository.list_categories(db, store_id))
    if category_id is None:
        category_ids = list(visible)
    elif category_id in visible:
        category_ids = _with_descendants(category_id, _children_map(visible))  # include sub-categories
    else:
        category_ids = []  # unknown or hidden category: empty result, no hint that it exists

    ids, total = await repository.search_product_ids(
        db,
        category_ids=category_ids,
        store_id=store_id,
        keyword=keyword.strip() if keyword and keyword.strip() else None,
        attrs=attrs,
        in_stock=in_stock,
        page=page,
        size=size,
    )
    cards = await repository.product_cards(db, ids)
    return PublicProductPageOut(
        items=[PublicProductOut(**cards[i]) for i in ids if i in cards],
        page=page,
        size=size,
        total=total,
        total_pages=(total + size - 1) // size,
    )

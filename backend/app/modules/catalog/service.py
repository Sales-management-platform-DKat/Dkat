"""Public product search and category tree (FR-07.1 - FR-07.3). No login.

Visibility:
- a category is visible when it and all its ancestors are ACTIVE (a sub-tree under an INACTIVE
  category is hidden, together with its products);
- a product is listed when it is ACTIVE, its category is visible and it has >= 1 ACTIVE variant.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.catalog import repository
from app.modules.catalog.schemas import PublicCategoryNode, PublicProductOut, PublicProductPageOut
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

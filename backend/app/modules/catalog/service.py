"""Public product search, product detail and category tree (FR-07.1 - FR-07.4). No login.

Visibility:
- a category is visible when it and all its ancestors are ACTIVE (an INACTIVE category hides its sub-tree
  together with the products in it);
- a product is listed when it is ACTIVE, its category is visible and it has >= 1 ACTIVE variant;
- hidden and unknown products / categories answer exactly like each other (404 / empty list).
Store: storeId is optional while the system has a single store; with several stores it is required.
"""
from fastapi import HTTPException
from sqlalchemy.engine import Connection

from app.modules.catalog import repository
from app.modules.catalog.schemas import (
    PublicAttributeValue, PublicBranch, PublicBranchAvailability, PublicCategoryNode, PublicCategoryRef,
    PublicProduct, PublicProductDetail, PublicProductPage, PublicVariant,
)

MAX_ATTR_FILTERS = 5


def invalid(field: str, message: str) -> HTTPException:
    return HTTPException(422, {"code": "INVALID_FILTER", "message": message, "details": [{"field": field, "reason": message}]})


def parse_attr_filters(raw: list[str]) -> list[tuple[str, str]]:
    """`attr=Màu:Đỏ&attr=Size:M` -> [("Màu", "Đỏ"), ("Size", "M")] (case-insensitive, column collation)."""
    if len(raw) > MAX_ATTR_FILTERS:
        raise invalid("attr", f"Tối đa {MAX_ATTR_FILTERS} bộ lọc thuộc tính")
    result = []
    for item in raw:
        name, sep, value = item.partition(":")
        name, value = name.strip(), value.strip()
        if not sep or not name or not value or len(name) > 100 or len(value) > 255:
            raise invalid("attr", f"Bộ lọc thuộc tính phải có dạng tên:giá trị, ví dụ attr=Màu:Đỏ (nhận được {item!r})")
        result.append((name, value))
    return result


def resolve_store(db: Connection, store_id: int | None) -> int:
    if store_id is not None:
        return store_id
    stores = repository.store_ids(db)
    if len(stores) == 1:
        return stores[0]
    raise invalid("storeId", "Hệ thống có nhiều cửa hàng: cần tham số storeId" if stores else "Chưa có cửa hàng nào")


def _visible(categories: list[dict]) -> dict[int, dict]:
    by_id = {c["id"]: c for c in categories}
    memo: dict[int, bool] = {}

    def ok(cid: int, seen: frozenset = frozenset()) -> bool:
        if cid in memo:
            return memo[cid]
        c = by_id.get(cid)
        if c is None or c["status"] != "ACTIVE" or cid in seen:  # missing parent or a cycle -> hidden
            return False
        memo[cid] = c["parent_id"] is None or ok(c["parent_id"], seen | {cid})
        return memo[cid]

    return {cid: c for cid, c in by_id.items() if ok(cid)}


def _children(visible: dict[int, dict]) -> dict[int | None, list[dict]]:
    out: dict[int | None, list[dict]] = {}
    for c in visible.values():  # keeps the SQL order (Vietnamese-aware collation)
        out.setdefault(c["parent_id"], []).append(c)
    return out


def category_tree(db: Connection, store_id: int | None) -> list[PublicCategoryNode]:
    store = resolve_store(db, store_id)
    kids = _children(_visible(repository.categories(db, store)))

    def build(c: dict) -> PublicCategoryNode:
        return PublicCategoryNode(id=c["id"], name=c["name"], children=[build(x) for x in kids.get(c["id"], [])])

    return [build(c) for c in kids.get(None, [])]


def search_products(db: Connection, *, store_id: int | None, keyword: str | None, category_id: int | None,
                    attrs: list[tuple[str, str]], in_stock: bool | None, page: int, size: int) -> PublicProductPage:
    store = resolve_store(db, store_id)
    visible = _visible(repository.categories(db, store))
    if category_id is None:
        category_ids = list(visible)
    elif category_id in visible:  # the category and all its sub-categories
        kids, ids, stack = _children(visible), [], [category_id]
        while stack:
            cid = stack.pop()
            ids.append(cid)
            stack.extend(c["id"] for c in kids.get(cid, []))
        category_ids = ids
    else:
        category_ids = []  # unknown or hidden: empty result, no hint that it exists
    ids, total = repository.search_page(db, store, category_ids, keyword=keyword.strip() if keyword and keyword.strip() else None,
                                        attrs=attrs, in_stock=in_stock, page=page, size=size)
    cards = repository.product_cards(db, ids)
    return PublicProductPage(
        items=[PublicProduct(id=i, name=cards[i]["name"], image_url=cards[i]["image_url"],
                             category=PublicCategoryRef(id=cards[i]["category_id"], name=cards[i]["category_name"]),
                             price_min=float(cards[i]["price_min"]), price_max=float(cards[i]["price_max"]),
                             in_stock=bool(cards[i]["in_stock"])) for i in ids if i in cards],
        page=page, size=size, total=total, total_pages=(total + size - 1) // size)


def product_detail(db: Connection, product_id: int) -> PublicProductDetail:
    row = repository.product(db, product_id)
    variants = repository.active_variants(db, product_id) if row else []
    if (row is None or row["status"] != "ACTIVE" or not variants
            or row["category_id"] not in _visible(repository.categories(db, row["store_id"]))):
        raise HTTPException(404, {"code": "PRODUCT_NOT_FOUND", "message": "Không tìm thấy sản phẩm"})
    variant_ids = [v["variant_id"] for v in variants]
    branch_ids = [b["branchId"] for b in repository.active_branches(db, row["store_id"])]
    attributes = repository.variant_attributes(db, variant_ids)
    available = repository.available_pairs(db, variant_ids, branch_ids)
    prices = [float(v["price"]) for v in variants]
    return PublicProductDetail(
        id=row["product_id"], name=row["name"], description=row["description"], image_url=row["image_url"],
        category=PublicCategoryRef(id=row["category_id"], name=row["category_name"]),
        price_min=min(prices), price_max=max(prices), in_stock=bool(available),
        variants=[PublicVariant(
            id=v["variant_id"], sku=v["sku"], name=v["variant_name"], price=float(v["price"]),
            attributes=[PublicAttributeValue(name=n, value=val) for n, val in attributes.get(v["variant_id"], [])],
            branches=[PublicBranchAvailability(branch_id=b, availability="IN_STOCK" if (v["variant_id"], b) in available else "OUT_OF_STOCK")
                      for b in branch_ids],
        ) for v in variants])


def branches(db: Connection, store_id: int | None) -> list[PublicBranch]:
    return [PublicBranch(branch_id=b["branchId"], name=b["name"], address=b["address"], phone=b["phone"])
            for b in repository.active_branches(db, resolve_store(db, store_id))]

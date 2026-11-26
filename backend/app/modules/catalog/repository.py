"""SQL for the public catalog (FR-07). Read-only.

Available stock (same formula as the inventory and pre-order modules):
    inventory.quantity - SUM(preorder_items.allocated_quantity of WAITING_STOCK / READY / NOTIFIED
                             pre-orders at the same branch for the same variant)
Only ACTIVE branches and ACTIVE variants count.

Index use (checked with EXPLAIN by scripts/check_public_catalog.py):
- store / category filter -> products.ix_products_category_status (store_id, category_id, status)
- variants of a product   -> product_variants.ix_variants_product_status (product_id, status)
- stock of a variant      -> inventory variant_id index (FK) or uq_inventory_branch_variant (branch_id, variant_id)
- reservations            -> preorder_items.ix_preorder_items_variant_order (variant_id, preorder_id), preorders PRIMARY
- attribute filter        -> variant_attribute_values.uq_variant_attribute (variant_id, attribute_id)
The keyword uses LIKE '%...%', which no B-tree index can serve: it scans the products of ONE store
(already narrowed by the store / category index).
"""
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

OPEN = "'WAITING_STOCK', 'READY', 'NOTIFIED'"

# EXISTS: an ACTIVE variant of product {p} has available stock > 0 at an ACTIVE branch
HAS_STOCK = f"""EXISTS (
    SELECT 1 FROM product_variants sv
    JOIN inventory si ON si.variant_id = sv.variant_id
    JOIN branches sb ON sb.branch_id = si.branch_id AND sb.status = 'ACTIVE'
    WHERE sv.product_id = {{p}} AND sv.status = 'ACTIVE'
      AND si.quantity > COALESCE((
          SELECT SUM(pi.allocated_quantity) FROM preorder_items pi
          JOIN preorders po ON po.preorder_id = pi.preorder_id
          WHERE pi.variant_id = si.variant_id AND po.branch_id = si.branch_id AND po.status IN ({OPEN})), 0)
)"""


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def store_ids(db: Connection) -> list[int]:
    return list(db.execute(text("SELECT store_id FROM stores ORDER BY store_id LIMIT 2")).scalars())


def categories(db: Connection, store_id: int) -> list[dict]:
    # ORDER BY name uses the column collation (Vietnamese aware: "Áo" before "Quần")
    return [dict(r) for r in db.execute(text("""
        SELECT category_id AS id, parent_category_id AS parent_id, name, status FROM categories
        WHERE store_id = :s ORDER BY name, category_id"""), {"s": store_id}).mappings()]


def search_statement(*, keyword: str | None, attrs: list[tuple[str, str]], in_stock: bool | None) -> tuple[str, dict]:
    """WHERE part of the product search (products p). Category ids are bound as :cats (expanding)."""
    where = ["p.store_id = :s", "p.category_id IN :cats", "p.status = 'ACTIVE'"]
    params: dict = {}
    variant = ["v.product_id = p.product_id", "v.status = 'ACTIVE'"]
    for i, (name, value) in enumerate(attrs):  # the SAME variant must have every requested attribute value
        variant.append(f"""EXISTS (SELECT 1 FROM variant_attribute_values va
                                   JOIN attributes a ON a.attribute_id = va.attribute_id AND a.status = 'ACTIVE'
                                   WHERE va.variant_id = v.variant_id AND a.name = :an{i} AND va.value = :av{i})""")
        params[f"an{i}"], params[f"av{i}"] = name, value
    # a product without an ACTIVE (matching) variant has no price: never listed
    where.append(f"EXISTS (SELECT 1 FROM product_variants v WHERE {' AND '.join(variant)})")
    if keyword:
        where.append("p.name LIKE :kw ESCAPE '!'")
        params["kw"] = f"%{_escape_like(keyword)}%"
    if in_stock is True:
        where.append(HAS_STOCK.format(p="p.product_id"))
    elif in_stock is False:
        where.append("NOT " + HAS_STOCK.format(p="p.product_id"))
    return " AND ".join(where), params


def search_page(db: Connection, store_id: int, category_ids: list[int], *, keyword: str | None,
                attrs: list[tuple[str, str]], in_stock: bool | None, page: int, size: int) -> tuple[list[int], int]:
    if not category_ids:
        return [], 0
    where, params = search_statement(keyword=keyword, attrs=attrs, in_stock=in_stock)
    params.update(s=store_id, cats=category_ids)
    total = db.execute(text(f"SELECT COUNT(*) FROM products p WHERE {where}")
                       .bindparams(bindparam("cats", expanding=True)), params).scalar_one()
    ids = db.execute(text(f"SELECT p.product_id FROM products p WHERE {where} ORDER BY p.name, p.product_id LIMIT :lim OFFSET :off")
                     .bindparams(bindparam("cats", expanding=True)), {**params, "lim": size, "off": (page - 1) * size}).scalars()
    return list(ids), int(total)


def product_cards(db: Connection, product_ids: list[int]) -> dict[int, dict]:
    """Public fields only: name, image, category, price range of ACTIVE variants, in-stock flag."""
    if not product_ids:
        return {}
    rows = db.execute(text(f"""
        SELECT p.product_id, p.name, p.image_url, c.category_id, c.name AS category_name,
               (SELECT MIN(v.price) FROM product_variants v WHERE v.product_id = p.product_id AND v.status = 'ACTIVE') AS price_min,
               (SELECT MAX(v.price) FROM product_variants v WHERE v.product_id = p.product_id AND v.status = 'ACTIVE') AS price_max,
               {HAS_STOCK.format(p="p.product_id")} AS in_stock
        FROM products p JOIN categories c ON c.category_id = p.category_id
        WHERE p.product_id IN :ids""").bindparams(bindparam("ids", expanding=True)), {"ids": product_ids}).mappings()
    return {r["product_id"]: dict(r) for r in rows}


def product(db: Connection, product_id: int) -> dict | None:
    row = db.execute(text("""
        SELECT p.product_id, p.store_id, p.status, p.name, p.description, p.image_url, p.category_id, c.name AS category_name
        FROM products p JOIN categories c ON c.category_id = p.category_id WHERE p.product_id = :id"""),
        {"id": product_id}).mappings().first()
    return dict(row) if row else None


def active_variants(db: Connection, product_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(text("""
        SELECT variant_id, sku, variant_name, price FROM product_variants
        WHERE product_id = :id AND status = 'ACTIVE' ORDER BY variant_id"""), {"id": product_id}).mappings()]


def variant_attributes(db: Connection, variant_ids: list[int]) -> dict[int, list[tuple[str, str]]]:
    if not variant_ids:
        return {}
    out: dict[int, list[tuple[str, str]]] = {}
    for r in db.execute(text("""
            SELECT va.variant_id, a.name, va.value FROM variant_attribute_values va
            JOIN attributes a ON a.attribute_id = va.attribute_id AND a.status = 'ACTIVE'
            WHERE va.variant_id IN :ids ORDER BY va.variant_id, a.name""").bindparams(bindparam("ids", expanding=True)),
            {"ids": variant_ids}).mappings():
        out.setdefault(r["variant_id"], []).append((r["name"], r["value"]))
    return out


def active_branches(db: Connection, store_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(text("""
        SELECT branch_id AS branchId, name, address, phone FROM branches
        WHERE store_id = :s AND status = 'ACTIVE' ORDER BY branch_id"""), {"s": store_id}).mappings()]


AVAILABLE_PAIRS = f"""
    SELECT i.variant_id, i.branch_id FROM inventory i
    WHERE i.variant_id IN :vids AND i.branch_id IN :bids
      AND i.quantity > COALESCE((
          SELECT SUM(pi.allocated_quantity) FROM preorder_items pi JOIN preorders po ON po.preorder_id = pi.preorder_id
          WHERE pi.variant_id = i.variant_id AND po.branch_id = i.branch_id AND po.status IN ({OPEN})), 0)"""


def available_pairs(db: Connection, variant_ids: list[int], branch_ids: list[int]) -> set[tuple[int, int]]:
    """(variant_id, branch_id) with available stock > 0. A missing inventory row = not available."""
    if not variant_ids or not branch_ids:
        return set()
    rows = db.execute(text(AVAILABLE_PAIRS).bindparams(bindparam("vids", expanding=True), bindparam("bids", expanding=True)),
                      {"vids": variant_ids, "bids": branch_ids}).all()
    return {(v, b) for v, b in rows}

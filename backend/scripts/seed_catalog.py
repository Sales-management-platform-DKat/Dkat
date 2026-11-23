"""Seed catalog data for the public product API (idempotent). Run AFTER scripts.seed_auth.

Run from backend/:  python -m scripts.seed_catalog

Every row covers one rule of GET /public/products and GET /public/categories:
  Thời trang > Áo, Quần          visible category tree
  Ngừng kinh doanh (INACTIVE) > Hàng thanh lý (ACTIVE)   whole sub-tree hidden
  SP-MAU-01 Áo thun mẫu          in stock (seed_auth: 10 at CN01-CN03), attributes Size S/M, Màu Trắng
  SP-MAU-02 Áo sơ mi mẫu         price range 250k-280k; INACTIVE variant at 10k must not count;
                                 cost price 123456.78 must never be returned
  SP-MAU-03 Quần kaki mẫu        stock 2 at CN01 fully allocated to PO-SEED-0001 -> inStock false
  SP-MAU-04 Áo ngừng bán mẫu     INACTIVE product -> never listed
  SP-MAU-05 Áo thanh lý mẫu      ACTIVE product in a hidden category -> never listed
"""
import asyncio

from sqlalchemy import text

from app.db.session import close_engine, standalone_transaction

CATEGORIES = [  # (name, parent name, status) - parents first
    ("Thời trang", None, "ACTIVE"),
    ("Áo", "Thời trang", "ACTIVE"),
    ("Quần", "Thời trang", "ACTIVE"),
    ("Ngừng kinh doanh", None, "INACTIVE"),
    ("Hàng thanh lý", "Ngừng kinh doanh", "ACTIVE"),
]
ATTRIBUTES = ["Màu", "Size"]
COST = 123456.78
# code, name, category, status, image, variants: (sku, variant name, price, cost, status, {attr: value}, {branch: qty})
PRODUCTS = [
    (
        "SP-MAU-02", "Áo sơ mi mẫu", "Áo", "ACTIVE", "https://example.com/img/ao-so-mi.jpg",
        [
            ("SP-MAU-02-XANH-M", "Áo sơ mi mẫu - Xanh M", 250000, COST, "ACTIVE", {"Màu": "Xanh", "Size": "M"}, {"CN02": 5}),
            ("SP-MAU-02-DO-L", "Áo sơ mi mẫu - Đỏ L", 280000, COST, "ACTIVE", {"Màu": "Đỏ", "Size": "L"}, {"CN01": 0}),
            ("SP-MAU-02-CU", "Áo sơ mi mẫu - mẫu cũ", 10000, COST, "INACTIVE", {"Màu": "Xanh", "Size": "S"}, {"CN01": 99}),
        ],
    ),
    (
        "SP-MAU-03", "Quần kaki mẫu", "Quần", "ACTIVE", None,
        [("SP-MAU-03-M", "Quần kaki mẫu - Đen M", 300000, COST, "ACTIVE", {"Màu": "Đen", "Size": "M"}, {"CN01": 2})],
    ),
    (
        "SP-MAU-04", "Áo ngừng bán mẫu", "Áo", "INACTIVE", None,
        [("SP-MAU-04-M", "Áo ngừng bán mẫu - M", 90000, None, "ACTIVE", {"Size": "M"}, {"CN01": 10})],
    ),
    (
        "SP-MAU-05", "Áo thanh lý mẫu", "Hàng thanh lý", "ACTIVE", None,
        [("SP-MAU-05-M", "Áo thanh lý mẫu - M", 50000, None, "ACTIVE", {"Size": "M"}, {"CN01": 10})],
    ),
]
EXISTING_VARIANT_ATTRS = {"SP-MAU-01-S": {"Size": "S", "Màu": "Trắng"}, "SP-MAU-01-M": {"Size": "M", "Màu": "Trắng"}}
PREORDER_CODE = "PO-SEED-0001"
RESERVED_SKU, RESERVED_QTY = "SP-MAU-03-M", 2


async def _scalar(db, sql: str, params: dict):
    return (await db.execute(text(sql), params)).scalar()


async def main() -> None:
    async with standalone_transaction() as db:
        owner = (await db.execute(text("SELECT user_id, store_id FROM users WHERE username = 'owner01'"))).first()
        if owner is None:
            raise SystemExit("Run python -m scripts.seed_auth first")
        owner_id, store_id = owner
        branches = dict((await db.execute(text("SELECT branch_code, branch_id FROM branches WHERE store_id = :s"), {"s": store_id})).all())

        categories: dict[str, int] = {}
        for name, parent, status in CATEGORIES:
            cid = await _scalar(db, "SELECT category_id FROM categories WHERE store_id = :s AND name = :n", {"s": store_id, "n": name})
            if cid is None:
                cid = (
                    await db.execute(
                        text("INSERT INTO categories (store_id, parent_category_id, name, status) VALUES (:s, :p, :n, :st)"),
                        {"s": store_id, "p": categories.get(parent), "n": name, "st": status},
                    )
                ).lastrowid
                print("create category")
            categories[name] = cid

        attributes: dict[str, int] = {}
        for name in ATTRIBUTES:
            aid = await _scalar(db, "SELECT attribute_id FROM attributes WHERE store_id = :s AND name = :n", {"s": store_id, "n": name})
            if aid is None:
                aid = (await db.execute(text("INSERT INTO attributes (store_id, name) VALUES (:s, :n)"), {"s": store_id, "n": name})).lastrowid
                print("create attribute")
            attributes[name] = aid

        async def set_attrs(variant_id: int, values: dict[str, str]) -> None:
            for attr, value in values.items():
                await db.execute(
                    text("INSERT IGNORE INTO variant_attribute_values (variant_id, attribute_id, value) VALUES (:v, :a, :val)"),
                    {"v": variant_id, "a": attributes[attr], "val": value},
                )

        for sku, values in EXISTING_VARIANT_ATTRS.items():
            vid = await _scalar(db, "SELECT variant_id FROM product_variants WHERE sku = :sku", {"sku": sku})
            if vid is not None:
                await set_attrs(vid, values)

        for code, name, category, status, image, variants in PRODUCTS:
            pid = await _scalar(db, "SELECT product_id FROM products WHERE store_id = :s AND product_code = :c", {"s": store_id, "c": code})
            if pid is None:
                pid = (
                    await db.execute(
                        text(
                            "INSERT INTO products (store_id, category_id, product_code, name, image_url, status, created_by) "
                            "VALUES (:s, :cat, :c, :n, :img, :st, :u)"
                        ),
                        {"s": store_id, "cat": categories[category], "c": code, "n": name, "img": image, "st": status, "u": owner_id},
                    )
                ).lastrowid
                print(f"create product {code}")
            for sku, vname, price, cost, vstatus, attrs, stock in variants:
                await db.execute(
                    text(
                        "INSERT IGNORE INTO product_variants (product_id, sku, variant_name, price, cost_price, status) "
                        "VALUES (:p, :sku, :n, :price, :cost, :st)"
                    ),
                    {"p": pid, "sku": sku, "n": vname, "price": price, "cost": cost, "st": vstatus},
                )
                vid = await _scalar(db, "SELECT variant_id FROM product_variants WHERE sku = :sku", {"sku": sku})
                await set_attrs(vid, attrs)
                for branch_code, qty in stock.items():
                    await db.execute(
                        text("INSERT IGNORE INTO inventory (branch_id, variant_id, quantity) VALUES (:b, :v, :q)"),
                        {"b": branches[branch_code], "v": vid, "q": qty},
                    )

        # PO-SEED-0001 (WAITING_STOCK at CN01) holds the whole CN01 stock of SP-MAU-03-M
        preorder_id = await _scalar(db, "SELECT preorder_id FROM preorders WHERE preorder_code = :c", {"c": PREORDER_CODE})
        vid = await _scalar(db, "SELECT variant_id FROM product_variants WHERE sku = :sku", {"sku": RESERVED_SKU})
        if preorder_id and vid and not await _scalar(
            db, "SELECT 1 FROM preorder_items WHERE preorder_id = :p AND variant_id = :v", {"p": preorder_id, "v": vid}
        ):
            await db.execute(
                text(
                    "INSERT INTO preorder_items (preorder_id, variant_id, product_name_snapshot, sku_snapshot, unit_price, "
                    "quantity, allocated_quantity, line_total) VALUES (:p, :v, 'Quần kaki mẫu', :sku, 300000, :q, :q, :total)"
                ),
                {"p": preorder_id, "v": vid, "sku": RESERVED_SKU, "q": RESERVED_QTY, "total": 300000 * RESERVED_QTY},
            )
            print("create preorder item (stock fully allocated)")
    await close_engine()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

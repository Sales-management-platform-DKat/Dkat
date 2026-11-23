"""Seed test accounts for the auth API (idempotent: re-running skips existing usernames).

Run from backend/:  python -m scripts.seed_auth

Accounts (password for all: Dkat@1234):
  owner01     OWNER     ACTIVE  -> all branches of the store
  manager01   MANAGER   ACTIVE  -> CN01, CN02
  staff01     EMPLOYEE  ACTIVE  -> CN01
  locked01    EMPLOYEE  LOCKED  -> CN01

Branch CN03 is assigned to nobody (only OWNER sees it): used to test the RBAC branch scope.
Category "Danh mục mẫu" is used to test POST /products.
Product SP-MAU-01 (2 ACTIVE variants) and pre-order PO-SEED-0001 (WAITING_STOCK at CN01) are used
to test the branch API (inventory rows for a new branch, refusing to deactivate CN01).
"""
import asyncio

from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import close_engine, standalone_transaction

DEFAULT_PASSWORD = "Dkat@1234"
STORE_NAME = "DKat Demo Store"
BRANCHES = [
    ("CN01", "Chi nhánh Quận 1", "12 Lê Lợi, Q.1, TP.HCM"),
    ("CN02", "Chi nhánh Cầu Giấy", "88 Xuân Thủy, Cầu Giấy, Hà Nội"),
    ("CN03", "Chi nhánh Hải Châu", "45 Bạch Đằng, Hải Châu, Đà Nẵng"),
]
BRANCH_PHONES = {"CN01": "028 3822 1001", "CN02": "024 3756 1002", "CN03": "0236 382 1003"}
CATEGORY_NAME = "Danh mục mẫu"
PRODUCT_CODE = "SP-MAU-01"
VARIANTS = [("SP-MAU-01-S", "Áo thun mẫu - Size S"), ("SP-MAU-01-M", "Áo thun mẫu - Size M")]
PREORDER_CODE = "PO-SEED-0001"
USERS = [
    ("owner01", "Nguyễn Văn Chủ", "OWNER", "ACTIVE", []),
    ("manager01", "Trần Thị Quản Lý", "MANAGER", "ACTIVE", ["CN01", "CN02"]),
    ("staff01", "Lê Văn Nhân Viên", "EMPLOYEE", "ACTIVE", ["CN01"]),
    ("locked01", "Phạm Bị Khóa", "EMPLOYEE", "LOCKED", ["CN01"]),
]


async def _seed_catalog_and_preorder(db, store_id: int, branch_ids: dict[str, int]) -> None:
    """Sample product with 2 ACTIVE variants (stock 10 at CN01-CN03) and one open pre-order at CN01.

    Used by the branch API tests: a new branch must get inventory rows for these variants, and
    CN01 cannot be deactivated while PO-SEED-0001 is WAITING_STOCK.
    """
    owner_id = (await db.execute(text("SELECT user_id FROM users WHERE username = 'owner01'"))).scalar_one()
    category_id = (
        await db.execute(
            text("SELECT category_id FROM categories WHERE store_id = :s AND name = :n"), {"s": store_id, "n": CATEGORY_NAME}
        )
    ).scalar_one()

    product_id = (
        await db.execute(text("SELECT product_id FROM products WHERE store_id = :s AND product_code = :c"), {"s": store_id, "c": PRODUCT_CODE})
    ).scalar()
    if product_id is None:
        product_id = (
            await db.execute(
                text(
                    "INSERT INTO products (store_id, category_id, product_code, name, created_by) VALUES (:s, :cat, :c, :n, :u)"
                ),
                {"s": store_id, "cat": category_id, "c": PRODUCT_CODE, "n": "Áo thun mẫu", "u": owner_id},
            )
        ).lastrowid
        print(f"create product {PRODUCT_CODE}")

    for sku, variant_name in VARIANTS:
        await db.execute(
            text(
                "INSERT IGNORE INTO product_variants (product_id, sku, variant_name, price) VALUES (:p, :sku, :n, 150000)"
            ),
            {"p": product_id, "sku": sku, "n": variant_name},
        )
        variant_id = (await db.execute(text("SELECT variant_id FROM product_variants WHERE sku = :sku"), {"sku": sku})).scalar_one()
        for branch_id in branch_ids.values():
            await db.execute(
                text("INSERT IGNORE INTO inventory (branch_id, variant_id, quantity) VALUES (:b, :v, 10)"),
                {"b": branch_id, "v": variant_id},
            )

    result = await db.execute(
        text(
            "INSERT IGNORE INTO preorders (preorder_code, branch_id, customer_name, customer_phone, total_amount, status) "
            "VALUES (:c, :b, :n, '0900000000', 150000, 'WAITING_STOCK')"
        ),
        {"c": PREORDER_CODE, "b": branch_ids["CN01"], "n": "Khách đặt trước mẫu"},
    )
    if result.rowcount:
        print(f"create preorder {PREORDER_CODE} (WAITING_STOCK at CN01)")


async def main() -> None:
    pw_hash = await hash_password(DEFAULT_PASSWORD)
    async with standalone_transaction() as db:
        # stores.owner_user_id -> users and users.store_id -> stores reference each other
        await db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        store_id = (await db.execute(text("SELECT store_id FROM stores WHERE name = :n"), {"n": STORE_NAME})).scalar()
        if store_id is None:
            store_id = (
                await db.execute(text("INSERT INTO stores (name, owner_user_id) VALUES (:n, 0)"), {"n": STORE_NAME})
            ).lastrowid

        branch_ids: dict[str, int] = {}
        for code, name, address in BRANCHES:
            await db.execute(
                text(
                    "INSERT IGNORE INTO branches (store_id, branch_code, name, address) VALUES (:s, :c, :n, :a)"
                ),
                {"s": store_id, "c": code, "n": name, "a": address},
            )
            branch_ids[code] = (
                await db.execute(
                    text("SELECT branch_id FROM branches WHERE store_id = :s AND branch_code = :c"),
                    {"s": store_id, "c": code},
                )
            ).scalar_one()
            # Contact phone shown in notifications ("liên hệ <SĐT cửa hàng>"); never overwrites a real one
            await db.execute(
                text("UPDATE branches SET phone = :p WHERE branch_id = :b AND phone IS NULL"),
                {"p": BRANCH_PHONES[code], "b": branch_ids[code]},
            )

        if (
            await db.execute(
                text("SELECT 1 FROM categories WHERE store_id = :s AND name = :n"), {"s": store_id, "n": CATEGORY_NAME}
            )
        ).first() is None:
            await db.execute(
                text("INSERT INTO categories (store_id, name) VALUES (:s, :n)"), {"s": store_id, "n": CATEGORY_NAME}
            )
            print("create sample category")  # ASCII only: the Windows console may not print Vietnamese

        for username, full_name, role, status, codes in USERS:
            user_id = (await db.execute(text("SELECT user_id FROM users WHERE username = :u"), {"u": username})).scalar()
            if user_id is not None:
                print(f"skip   {username} (exists)")
                continue
            user_id = (
                await db.execute(
                    text(
                        "INSERT INTO users (store_id, full_name, username, password_hash, role, status) "
                        "VALUES (:s, :f, :u, :p, :r, :st)"
                    ),
                    {"s": store_id, "f": full_name, "u": username, "p": pw_hash, "r": role, "st": status},
                )
            ).lastrowid
            for code in codes:
                await db.execute(
                    text("INSERT IGNORE INTO user_branches (user_id, branch_id) VALUES (:u, :b)"),
                    {"u": user_id, "b": branch_ids[code]},
                )
            if role == "OWNER":
                await db.execute(text("UPDATE stores SET owner_user_id = :u WHERE store_id = :s"), {"u": user_id, "s": store_id})
            print(f"create {username} ({role}, {status})")

        await _seed_catalog_and_preorder(db, store_id, branch_ids)

        await db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    await close_engine()
    print(f"Done. Password for all seeded accounts: {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())

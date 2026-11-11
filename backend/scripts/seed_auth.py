"""Seed test accounts for the auth API (idempotent: re-running skips existing usernames).

Run from backend/:  python -m scripts.seed_auth

Accounts (password for all: Dkat@1234):
  owner01     OWNER     ACTIVE  -> all branches of the store
  manager01   MANAGER   ACTIVE  -> CN01, CN02
  staff01     EMPLOYEE  ACTIVE  -> CN01
  locked01    EMPLOYEE  LOCKED  -> CN01
"""
import asyncio

from sqlalchemy import text

from app.core.security import hash_password
from app.db.session import close_engine, standalone_transaction

DEFAULT_PASSWORD = "Dkat@1234"
STORE_NAME = "DKat Demo Store"
BRANCHES = [("CN01", "Chi nhánh Quận 1", "12 Lê Lợi, Q.1, TP.HCM"), ("CN02", "Chi nhánh Cầu Giấy", "88 Xuân Thủy, Cầu Giấy, Hà Nội")]
USERS = [
    ("owner01", "Nguyễn Văn Chủ", "OWNER", "ACTIVE", []),
    ("manager01", "Trần Thị Quản Lý", "MANAGER", "ACTIVE", ["CN01", "CN02"]),
    ("staff01", "Lê Văn Nhân Viên", "EMPLOYEE", "ACTIVE", ["CN01"]),
    ("locked01", "Phạm Bị Khóa", "EMPLOYEE", "LOCKED", ["CN01"]),
]


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

        await db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    await close_engine()
    print(f"Done. Password for all seeded accounts: {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())

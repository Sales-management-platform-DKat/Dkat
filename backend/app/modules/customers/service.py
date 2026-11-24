import re

from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalize_phone(phone: str) -> str:
    """Accept Vietnamese domestic / +84 numbers, with common display separators."""
    value = re.sub(r"[\s().-]", "", phone.strip())
    if value.startswith("+84"):
        value = "0" + value[3:]
    elif value.startswith("84"):
        value = "0" + value[2:]
    if not re.fullmatch(r"0[1-9][0-9]{8,9}", value):
        raise ValueError("Số điện thoại phải có 10–11 chữ số, bắt đầu bằng 0 hoặc dùng mã +84")
    return value


def upsert_customer_by_phone(
    db: Connection, *, store_id: int, full_name: str, phone: str,
    email: str | None = None, address: str | None = None,
) -> int:
    """Use the caller's transaction. Existing profiles are never overwritten by public input."""
    phone = normalize_phone(phone)
    db.execute(
        text("""
            INSERT INTO customers (store_id, full_name, phone, email, address)
            VALUES (:store, :name, :phone, :email, :address)
            ON DUPLICATE KEY UPDATE customer_id = customer_id
        """),
        {"store": store_id, "name": full_name, "phone": phone, "email": email, "address": address},
    )
    return db.execute(
        text("SELECT customer_id FROM customers WHERE store_id=:store AND phone=:phone"),
        {"store": store_id, "phone": phone},
    ).scalar_one()

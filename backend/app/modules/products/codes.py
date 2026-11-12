import re
import unicodedata
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.modules.products.catalog_transaction import CatalogConflict
from app.modules.products.code_config import (
    CATEGORY_CODE_PREFIXES,
    CATEGORY_PREFIX_MAX_LENGTH,
    DEFAULT_CATEGORY_PREFIX,
)


def code_words(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value.upper().replace("Đ", "D"))
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[A-Z0-9]+", without_accents)


def generate_product_code(db: Connection, store_id: int, category_name: str) -> str:
    words = code_words(category_name)
    fallback = "".join(word[0] for word in words) if len(words) > 1 else "".join(words)[:3]
    prefix = CATEGORY_CODE_PREFIXES.get(" ".join(words), fallback or DEFAULT_CATEGORY_PREFIX)
    prefix = prefix[:CATEGORY_PREFIX_MAX_LENGTH]

    # The caller holds the store lock before reading the existing sequence.
    codes = db.execute(
        text("""
            SELECT product_code FROM products
            WHERE store_id = :store AND product_code LIKE :pattern
        """),
        {"store": store_id, "pattern": f"{prefix}-%"},
    ).scalars()
    highest = 0
    for code in codes:
        number = code[len(prefix) + 1:]
        if number.isascii() and number.isdecimal():
            highest = max(highest, int(number))
    next_code = f"{prefix}-{highest + 1:04d}"
    if len(next_code) > 50:
        raise CatalogConflict("Product code sequence exhausted")
    return next_code


def generate_sku(product_code: str, attribute_values: Iterable[str]) -> str:
    parts = code_words(product_code) or [DEFAULT_CATEGORY_PREFIX]
    for value in attribute_values:
        parts.extend(code_words(value))
    return "-".join(parts)

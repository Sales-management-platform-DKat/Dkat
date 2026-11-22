import re

from sqlalchemy import text
from sqlalchemy.engine import Connection


def column_collation(db: Connection, table: str, column: str) -> str:
    collation = db.execute(text("""
        SELECT COLLATION_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME=:column
    """), {"table": table, "column": column}).scalar_one()
    if not isinstance(collation, str) or not re.fullmatch(r"[a-zA-Z0-9_]+", collation):
        raise ValueError("Unexpected column collation")
    return collation

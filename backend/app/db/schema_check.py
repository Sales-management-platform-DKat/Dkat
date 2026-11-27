"""Detects a MySQL/TiDB schema that lags behind the incremental scripts in database/.

There are no automatic migrations: a database created from an older 01_schema.sql keeps
its old shape until database/0N_*.sql are run, and create_all() never alters a table.
Queries then fail at run time with "Unknown column" (e.g. preorders.cancel_reason when
08_preorder_cancellation.sql was never applied). This module lists what each script adds
so startup, /health and scripts/db_migrate.py can name the exact script that is missing.

tests/test_schema_check.py keeps REQUIREMENTS in sync with the scripts.
"""
from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine


@dataclass(frozen=True)
class Requirement:
    kind: str  # table | column | index | enum
    table: str
    name: str = ""  # column / index name; for enum: the column
    value: str = ""  # enum value that must be allowed
    script: str = ""

    def describe(self) -> str:
        if self.kind == "table":
            return f"table {self.table}"
        if self.kind == "enum":
            return f"{self.table}.{self.name} value '{self.value}'"
        return f"{self.kind} {self.table}.{self.name}"


def _req(script: str, *items: tuple) -> list[Requirement]:
    return [Requirement(*item, script=script) for item in items]


REQUIREMENTS: list[Requirement] = [
    *_req("02_customers_for_sales.sql", ("table", "customers"), ("column", "sales_orders", "customer_id")),
    *_req("02_inventory_export.sql", ("enum", "inventory_movements", "movement_type", "EXPORT"),
          ("column", "inventory_movements", "export_reason")),
    *_req("03_inventory_movement_history.sql", ("index", "inventory_movements", "ix_movements_created_at_id")),
    *_req("05_sales_order_cancellation.sql", ("column", "sales_orders", "cancel_reason"),
          ("column", "sales_orders", "cancelled_at")),
    *_req("06_public_preorders.sql", ("column", "preorders", "customer_id"), ("column", "preorders", "customer_address"),
          ("column", "preorders", "note"), ("table", "preorder_request_limits")),
    *_req("07_preorder_fifo_expiry.sql", ("column", "preorders", "expires_at")),
    *_req("08_preorder_cancellation.sql", ("column", "preorders", "cancel_reason"), ("column", "preorders", "cancelled_at"),
          ("index", "preorders", "ix_preorders_expiry")),
    *_req("09_notification_retry.sql", ("column", "notifications", "event_type"), ("column", "notifications", "retry_count"),
          ("column", "notifications", "last_attempt_at"), ("index", "notifications", "ix_notifications_retry")),
]


def find_schema_drift(bind: Engine | Connection) -> list[Requirement]:
    """Requirements the connected MySQL/TiDB database does not meet. Read-only.

    SQLite is a local development database built by create_all(), not by these scripts,
    so it is not checked.
    """
    if bind.dialect.name != "mysql":
        return []
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    columns: dict[str, dict[str, object]] = {}
    indexes: dict[str, set[str]] = {}
    missing = []
    for requirement in REQUIREMENTS:
        if requirement.table not in tables:
            missing.append(requirement)
            continue
        if requirement.kind == "table":
            continue
        if requirement.kind == "index":
            if requirement.table not in indexes:
                indexes[requirement.table] = {index["name"] for index in inspector.get_indexes(requirement.table)}
            if requirement.name not in indexes[requirement.table]:
                missing.append(requirement)
            continue
        if requirement.table not in columns:
            columns[requirement.table] = {column["name"]: column["type"] for column in inspector.get_columns(requirement.table)}
        column_type = columns[requirement.table].get(requirement.name)
        if column_type is None:
            missing.append(requirement)
        elif requirement.kind == "enum" and requirement.value not in (getattr(column_type, "enums", None) or ()):
            missing.append(requirement)
    return missing


def missing_scripts(missing: list[Requirement]) -> list[str]:
    """Scripts to run, in the order they must be applied."""
    return sorted({requirement.script for requirement in missing})

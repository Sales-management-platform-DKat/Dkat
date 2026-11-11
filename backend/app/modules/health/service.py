"""Business logic for checking the database connection."""
import time

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.session import engine
from app.modules.health import repository

# The 18 tables of the DKat schema (dkat_db)
EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "stores", "branches", "users", "user_branches",
        "categories", "products", "product_variants", "attributes", "variant_attribute_values",
        "inventory", "inventory_movements",
        "sales_orders", "sales_order_items",
        "preorders", "preorder_items", "payments", "preorder_fulfillments",
        "notifications",
    }
)


async def check_database() -> dict:
    """Connect to MySQL and return detailed info.

    Raises AppError 503 if the connection fails.
    """
    start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            info = await repository.get_server_info(conn)
            tables = await repository.list_tables(conn)
    except Exception as exc:  # SQLAlchemyError, OSError, driver errors... -> all mean "cannot connect"
        raise AppError(
            503,
            "DATABASE_UNAVAILABLE",
            "Cannot connect to the database",
            {
                "host": f"{settings.DB_HOST}:{settings.DB_PORT}",
                "database": settings.DB_NAME,
                "reason": None if settings.is_production else str(getattr(exc, "orig", exc)),
            },
        ) from exc
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    missing = sorted(EXPECTED_TABLES - set(tables))
    pool = engine.pool
    return {
        "connected": True,
        "latency_ms": latency_ms,
        "host": f"{settings.DB_HOST}:{settings.DB_PORT}",
        "database": info["db_name"],
        "mysql_version": info["version"],
        "charset": info["charset"],
        "collation": info["collation"],
        "time_zone": info["time_zone"],
        "server_time": info["server_time"],
        "schema": {
            "table_count": len(tables),
            "expected_count": len(EXPECTED_TABLES),
            "is_complete": not missing,
            "missing_tables": missing,
            "tables": tables,
        },
        "pool": {
            "size": pool.size(),  # number of persistent connections allowed
            "in_use": pool.checkedout(),  # connections currently in use
            "idle": pool.checkedin(),  # open connections waiting in the pool
        },
    }

"""SQL queries for database health checks."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def get_server_info(conn: AsyncConnection) -> dict:
    row = (
        await conn.execute(
            text(
                "SELECT DATABASE() AS db_name, VERSION() AS version, "
                "@@character_set_database AS charset, @@collation_database AS collation, "
                "@@time_zone AS time_zone, NOW() AS server_time"
            )
        )
    ).mappings().one()
    return dict(row)


async def list_tables(conn: AsyncConnection) -> list[str]:
    rows = await conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
    )
    return [r[0] for r in rows]

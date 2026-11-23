"""Create the database DB_NAME (from .env) and all 20 tables. Safe to run again (IF NOT EXISTS).

Run from backend/:  python -m scripts.init_db
Needs only a running MySQL 8 server and DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME in .env:
no mysql command-line client is required. Uses database/00_schema_full.sql.
"""
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

SCHEMA = Path(__file__).resolve().parents[2] / "database" / "00_schema_full.sql"


def statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*\n", body) if s.strip()]


async def main() -> int:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", settings.DB_NAME):
        print(f"DB_NAME không hợp lệ: {settings.DB_NAME!r} (chỉ chữ, số, _)")
        return 2
    if not SCHEMA.exists():
        print(f"Không tìm thấy {SCHEMA}")
        return 2
    server_url = (
        f"mysql+aiomysql://{quote_plus(settings.DB_USER)}:{quote_plus(settings.DB_PASSWORD)}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/?charset=utf8mb4"
    )
    engine = create_async_engine(server_url)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            await conn.exec_driver_sql(f"USE `{settings.DB_NAME}`")
            for stmt in statements(SCHEMA.read_text(encoding="utf-8")):
                await conn.exec_driver_sql(stmt)  # driver-level: no ':name' bind parsing inside DDL
            tables = (await conn.exec_driver_sql("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")).all()
    except Exception as exc:  # connection refused, access denied...
        print(f"Lỗi: {exc.__class__.__name__}: {getattr(exc, 'orig', exc)}")
        print("Kiểm tra MySQL đã chạy và DB_HOST/DB_PORT/DB_USER/DB_PASSWORD trong backend/.env")
        return 1
    finally:
        await engine.dispose()
    print(f"OK: database {settings.DB_NAME} có {len(tables)} bảng")
    return 0 if len(tables) >= 20 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))

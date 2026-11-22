import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
ADMIN_TOKEN = os.getenv("DKAT_ADMIN_TOKEN", "")
ALLOW_EMPLOYEE_STOCK = os.getenv("ALLOW_EMPLOYEE_STOCK", "false").strip().lower() in {"1", "true", "yes", "on"}
try:
    PREORDER_READY_DAYS = int(os.getenv("PREORDER_READY_DAYS", "7"))
except ValueError:
    raise ValueError("PREORDER_READY_DAYS must be an integer from 1 to 365") from None
if not 1 <= PREORDER_READY_DAYS <= 365:
    raise ValueError("PREORDER_READY_DAYS must be an integer from 1 to 365")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DKAT_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if origin.strip()
]


def database_url() -> URL:
    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "dkat_app"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "dkat"),
        query={"charset": "utf8mb4"},
    )

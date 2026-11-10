import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


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

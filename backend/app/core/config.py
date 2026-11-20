import os
from pathlib import Path
from types import SimpleNamespace

import certifi
from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ADMIN_TOKEN = os.getenv("DKAT_ADMIN_TOKEN", "")
ALLOW_EMPLOYEE_STOCK = os.getenv("ALLOW_EMPLOYEE_STOCK", "false").strip().lower() in {"1", "true", "yes", "on"}
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DKAT_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

_database_fields = {
    "DB_HOST": os.getenv("DB_HOST"),
    "DB_PORT": os.getenv("DB_PORT"),
    "DB_USER": os.getenv("DB_USER"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    "DB_NAME": os.getenv("DB_NAME"),
}
_configured_fields = {key for key, value in _database_fields.items() if value}

if _configured_fields and len(_configured_fields) != len(_database_fields):
    missing = ", ".join(sorted(set(_database_fields) - _configured_fields))
    raise RuntimeError(f"Thiếu cấu hình database bắt buộc: {missing}")

if _configured_fields:
    DATABASE_URL = URL.create(
        "mysql+pymysql",
        username=_database_fields["DB_USER"],
        password=_database_fields["DB_PASSWORD"],
        host=_database_fields["DB_HOST"],
        port=int(_database_fields["DB_PORT"]),
        database=_database_fields["DB_NAME"],
    )
    DATABASE_CONNECT_ARGS = {
        "ssl_ca": os.getenv("DB_SSL_CA", certifi.where()),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
        "connect_timeout": 10,
    }
else:
    DATABASE_URL = os.getenv("DKAT_DATABASE_URL", "sqlite:///./dkat.db")
    DATABASE_CONNECT_ARGS = (
        {"check_same_thread": False}
        if DATABASE_URL.startswith("sqlite")
        else {}
    )

settings = SimpleNamespace(is_production=os.getenv("DKAT_ENV", "development").strip().lower() == "production")

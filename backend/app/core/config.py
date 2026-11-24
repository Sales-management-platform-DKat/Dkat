import os
from pathlib import Path
from types import SimpleNamespace

import certifi
from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ENVIRONMENT = os.getenv("DKAT_ENV", os.getenv("APP_ENV", "development")).strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

ADMIN_TOKEN = os.getenv("DKAT_ADMIN_TOKEN", "")
ALLOW_EMPLOYEE_STOCK = os.getenv("ALLOW_EMPLOYEE_STOCK", "false").strip().lower() in {"1", "true", "yes", "on"}
try:
    PREORDER_READY_DAYS = int(os.getenv("PREORDER_READY_DAYS", "7"))
except ValueError:
    raise ValueError("PREORDER_READY_DAYS must be an integer from 1 to 365") from None
if not 1 <= PREORDER_READY_DAYS <= 365:
    raise ValueError("PREORDER_READY_DAYS must be an integer from 1 to 365")
AUTH_SECRET_KEY = os.getenv("DKAT_AUTH_SECRET_KEY", os.getenv("SECRET_KEY", ""))
ACCESS_TOKEN_TTL_SECONDS = 15 * 60
SESSION_TTL_SECONDS = 12 * 60 * 60
REMEMBERED_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
COOKIE_SECURE = os.getenv("DKAT_COOKIE_SECURE", "auto").strip().casefold()
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
_required_database_fields = {"DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"}
_configured_fields = {key for key, value in _database_fields.items() if value is not None and value.strip()}
_missing_database_fields = {
    key for key in _required_database_fields
    if not (_database_fields[key] and _database_fields[key].strip())
}

if _configured_fields and _missing_database_fields:
    missing = ", ".join(sorted(_missing_database_fields))
    raise RuntimeError(f"Thiếu cấu hình database bắt buộc: {missing}")

if _required_database_fields.isdisjoint(_configured_fields) and IS_PRODUCTION and not os.getenv("DKAT_DATABASE_URL", "").strip():
    raise RuntimeError(
        "Production requires DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD "
        "or a non-SQLite DKAT_DATABASE_URL; SQLite fallback is disabled."
    )

if _configured_fields:
    if IS_PRODUCTION and not (_database_fields["DB_PASSWORD"] or "").strip():
        raise RuntimeError("Production requires a non-empty DB_PASSWORD.")
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
    if IS_PRODUCTION:
        try:
            production_database = make_url(DATABASE_URL)
        except Exception:
            raise RuntimeError("Production DKAT_DATABASE_URL is invalid.") from None
        if production_database.get_backend_name() not in {"mysql", "mariadb"}:
            raise RuntimeError(
                "Production requires the MySQL/MariaDB database engine used by this deployment; SQLite fallback is disabled."
            )
    DATABASE_CONNECT_ARGS = (
        {"check_same_thread": False}
        if DATABASE_URL.startswith("sqlite")
        else {}
    )

settings = SimpleNamespace(is_production=IS_PRODUCTION)

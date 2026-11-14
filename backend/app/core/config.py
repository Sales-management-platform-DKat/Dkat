"""Read configuration from environment variables / the .env file."""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # ---- App ----
    APP_NAME: str = "DKat API"
    APP_ENV: str = "development"  # development | production
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # ---- MySQL ----
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "dkat"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_RECYCLE: int = 1800  # seconds; must be shorter than MySQL wait_timeout
    DB_ECHO: bool = False  # True = print SQL statements

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

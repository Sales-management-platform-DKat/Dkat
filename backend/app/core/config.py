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

def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be a number") from None


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


settings = SimpleNamespace(
    is_production=IS_PRODUCTION,
    PREORDER_READY_DAYS=PREORDER_READY_DAYS,
    # ---- Pre-order notifications (FR-09). Empty SMTP_HOST / ESMS keys = channel not configured:
    # the send is recorded as FAILED with NOT_CONFIGURED and never breaks the business flow.
    SMTP_HOST=_env_str("SMTP_HOST"),
    SMTP_PORT=int(_env_float("SMTP_PORT", 587)),
    SMTP_SECURITY=_env_str("SMTP_SECURITY", "starttls").lower(),  # starttls | ssl | none
    SMTP_USERNAME=_env_str("SMTP_USERNAME"),
    SMTP_PASSWORD=_env_str("SMTP_PASSWORD"),  # Gmail: 16-character App Password
    SMTP_FROM_EMAIL=_env_str("SMTP_FROM_EMAIL"),
    SMTP_FROM_NAME=_env_str("SMTP_FROM_NAME", "DKat"),
    SMTP_TIMEOUT_SECONDS=_env_float("SMTP_TIMEOUT_SECONDS", 10.0),
    EMAIL_TEST_TO=_env_str("EMAIL_TEST_TO"),
    ESMS_API_KEY=_env_str("ESMS_API_KEY"),
    ESMS_SECRET_KEY=_env_str("ESMS_SECRET_KEY"),
    ESMS_BRANDNAME=_env_str("ESMS_BRANDNAME", "Baotrixemay"),
    ESMS_SMS_TYPE=_env_str("ESMS_SMS_TYPE", "2"),
    ESMS_SANDBOX=_env_bool("ESMS_SANDBOX", False),
    ESMS_CALLBACK_URL=_env_str("ESMS_CALLBACK_URL"),
    ESMS_BASE_URL=_env_str("ESMS_BASE_URL", "https://rest.esms.vn/MainService.svc/json"),
    SMS_UNICODE=_env_bool("SMS_UNICODE", False),
    SMS_MAX_PARTS=int(_env_float("SMS_MAX_PARTS", 3)),
    SMS_TIMEOUT_SECONDS=_env_float("SMS_TIMEOUT_SECONDS", 10.0),
    SMS_TEST_TO=_env_str("SMS_TEST_TO"),
    NOTIFY_SMS_CONFIRM_SECONDS=_env_float("NOTIFY_SMS_CONFIRM_SECONDS", 30.0),
    NOTIFY_SMS_POLL_SECONDS=_env_float("NOTIFY_SMS_POLL_SECONDS", 5.0),
    STORE_CONTACT_PHONE=_env_str("STORE_CONTACT_PHONE"),
    NOTIFY_RETRY_ENABLED=_env_bool("NOTIFY_RETRY_ENABLED", True),
    NOTIFY_RETRY_INTERVAL_SECONDS=_env_float("NOTIFY_RETRY_INTERVAL_SECONDS", 300.0),
    NOTIFY_MAX_RETRIES=int(_env_float("NOTIFY_MAX_RETRIES", 3)),
    NOTIFY_RETRY_BATCH=int(_env_float("NOTIFY_RETRY_BATCH", 50)),
)

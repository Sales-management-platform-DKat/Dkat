"""Read configuration from environment variables / the .env file."""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # ---- Auth ----
    JWT_SECRET: str = "dev-only-change-me-please-32-bytes-min"  # MUST be overridden in .env for production
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8
    BCRYPT_ROUNDS: int = 12  # cost factor, >= 10

    # ---- Public API (no login) ----
    PUBLIC_RATE_LIMIT_PER_MINUTE: int = 60  # per client IP, shared by all /public endpoints

    # ---- Email via SMTP (FR-09.2) ----
    SMTP_HOST: str = ""  # e.g. smtp.gmail.com; empty = email not configured (send_email returns NOT_CONFIGURED)
    SMTP_PORT: int = 587
    SMTP_SECURITY: str = "starttls"  # starttls (port 587) | ssl (port 465) | none (local test server only)
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""  # Gmail: a 16-character App Password, never the account password
    SMTP_FROM_EMAIL: str = ""  # Gmail requires the same address as SMTP_USERNAME
    SMTP_FROM_NAME: str = "DKat"
    SMTP_TIMEOUT_SECONDS: float = 10.0  # whole send (connect + login + send), not per step
    EMAIL_TEST_TO: str = ""  # default recipient of scripts/send_test_email.py (the team mailbox)

    # ---- SMS via eSMS.vn (FR-09.1) ----
    ESMS_API_KEY: str = ""
    ESMS_SECRET_KEY: str = ""
    ESMS_BRANDNAME: str = "Baotrixemay"  # eSMS test brandname; use your own once registered with the carriers
    ESMS_SMS_TYPE: str = "2"  # 2 = brandname customer care (CSKH)
    ESMS_SANDBOX: bool = False  # True: eSMS validates the request but sends nothing and charges nothing
    ESMS_CALLBACK_URL: str = ""  # optional webhook for the final delivery status
    ESMS_BASE_URL: str = "https://rest.esms.vn/MainService.svc/json"
    SMS_UNICODE: bool = False  # False: Vietnamese accents are removed before sending (cheaper, 160 chars/part)
    SMS_MAX_PARTS: int = 3  # longer content is refused (INVALID_INPUT)
    SMS_TIMEOUT_SECONDS: float = 10.0
    SMS_TEST_TO: str = ""  # default recipient of scripts/send_test_sms.py (the team phone)

    # ---- Pre-order notifications (FR-09.3, FR-09.4) ----
    # After eSMS accepts an SMS, wait up to this long for the carrier outcome: refused -> fall back to
    # email. 0 = trust the acceptance (no fallback on later carrier refusal).
    NOTIFY_SMS_CONFIRM_SECONDS: float = 30.0
    NOTIFY_SMS_POLL_SECONDS: float = 5.0
    # Message content (FR-09.6)
    PREORDER_READY_DAYS: int = 7  # same as the pre-order module: hold = ready_at + N days (when expires_at is NULL)
    STORE_CONTACT_PHONE: str = ""  # hotline used when the branch has no phone
    # Automatic retry of FAILED notifications (FR-09.5, NFR-10)
    NOTIFY_RETRY_ENABLED: bool = True  # background job started with the app
    NOTIFY_RETRY_INTERVAL_SECONDS: float = 300.0  # every 5 minutes
    NOTIFY_MAX_RETRIES: int = 3  # automatic re-sends per row; after that the row stays FAILED
    NOTIFY_RETRY_BATCH: int = 50  # rows per run

    # ---- Audit (NFR-08) ----
    CUSTOMER_ACCESS_LOG_FILE: str = "logs/customer_access.log"  # who viewed which customer profile

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{quote_plus(self.DB_USER)}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

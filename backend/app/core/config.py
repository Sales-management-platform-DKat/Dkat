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

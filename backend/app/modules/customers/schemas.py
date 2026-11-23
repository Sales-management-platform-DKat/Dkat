"""Request/response schemas for /customers (JSON uses camelCase)."""
import re
from datetime import datetime

from pydantic import Field, field_validator

from app.modules.auth.schemas import CamelModel

# Vietnamese mobile/landline in domestic form: 10 digits starting with 0 (e.g. 0901234567)
PHONE_PATTERN = re.compile(r"0\d{9}")
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MAX_PAGE_SIZE = 100


def normalize_phone(phone: str) -> str:
    """'0901 234 567', '090.123.4567', '+84901234567', '84901234567' -> '0901234567'.

    Raises ValueError unless the result is 10 digits starting with 0. Phones are stored in this
    form only, so the unique key (store_id, phone) really prevents duplicates.
    """
    value = re.sub(r"[\s().-]", "", phone.strip())
    if value.startswith("+84"):
        value = "0" + value[3:]
    elif value.startswith("84") and len(value) == 11:
        value = "0" + value[2:]
    if not PHONE_PATTERN.fullmatch(value):
        raise ValueError("Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0")
    return value


def _optional_text(v):
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("Must be a string")
    return v.strip() or None


class CustomerIn(CamelModel):
    """POST /customers and PUT /customers/{id} (PUT replaces every field)."""

    full_name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v  # "   " -> 422 (min_length)

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v):
        v = _optional_text(v)
        return normalize_phone(v) if v is not None else None

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        v = _optional_text(v)
        if v is not None and not EMAIL_PATTERN.fullmatch(v):
            raise ValueError("Email không đúng định dạng")
        return v

    @field_validator("address", "note", mode="before")
    @classmethod
    def strip_optional(cls, v):
        return _optional_text(v)


class CustomerOut(CamelModel):
    id: int
    full_name: str
    phone: str | None
    email: str | None
    address: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class CustomerPageOut(CamelModel):
    items: list[CustomerOut]
    page: int
    size: int
    total: int
    total_pages: int

"""Request/response schemas for /users (JSON uses camelCase).

UserOut has no password field on purpose: password_hash must never leave the server.
"""
import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES
from app.modules.auth.schemas import MIN_PASSWORD_LENGTH, CamelModel

# Roles that can be given through this API (OWNER accounts are never created or granted here)
ManagedRole = Literal["MANAGER", "EMPLOYEE"]
AnyRole = Literal["OWNER", "MANAGER", "EMPLOYEE"]
UserStatus = Literal["ACTIVE", "LOCKED"]
MAX_PAGE_SIZE = 100

USERNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{2,99}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_PATTERN = r"^\+?[0-9][0-9 .-]{5,18}$"


def _check_password(v: str) -> str:
    if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    return v


def _unique_branch_ids(v: list[int]) -> list[int]:
    if any(b <= 0 for b in v):
        raise ValueError("Branch ids must be positive")
    return sorted(set(v))


def _optional(v, pattern: str, message: str):
    """Blank -> None; otherwise must match `pattern`."""
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(message)
    v = v.strip()
    if not v:
        return None
    if not re.fullmatch(pattern, v):
        raise ValueError(message)
    return v


class _ProfileIn(CamelModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v  # "   " -> "" -> 422 min_length

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return _optional(v, EMAIL_PATTERN, "Invalid email")

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v):
        return _optional(v, PHONE_PATTERN, "Invalid phone number")


class UserCreateIn(_ProfileIn):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=BCRYPT_MAX_BYTES)
    role: ManagedRole
    branch_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("username", mode="before")
    @classmethod
    def check_username(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not re.fullmatch(USERNAME_PATTERN, v):
                raise ValueError("3-100 characters: letters, digits, '.', '_', '-' (must start with a letter or digit)")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _check_password(v)

    @field_validator("branch_ids")
    @classmethod
    def unique_branch_ids(cls, v: list[int]) -> list[int]:
        return _unique_branch_ids(v)


class UserBranchesIn(CamelModel):
    """PUT /users/{id}/branches: the complete new set of assigned branches (duplicates are merged)."""

    branch_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("branch_ids")
    @classmethod
    def unique_branch_ids(cls, v: list[int]) -> list[int]:
        return _unique_branch_ids(v)


class UserUpdateIn(_ProfileIn):
    """PUT /users/{id}: replaces fullName, email, phone. `role` omitted = unchanged (only OWNER may change it)."""

    role: ManagedRole | None = None


class UserStatusIn(CamelModel):
    status: UserStatus


class ResetPasswordIn(CamelModel):
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=BCRYPT_MAX_BYTES)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _check_password(v)


class AssignedBranchOut(CamelModel):
    id: int
    branch_code: str
    name: str
    status: str  # an INACTIVE assignment is kept but grants no access


class UserOut(CamelModel):
    id: int
    store_id: int
    username: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    status: str
    created_at: datetime
    branches: list[AssignedBranchOut]  # rows of user_branches. OWNER: [] (works on every branch, see /auth/me)


class UserPageOut(CamelModel):
    items: list[UserOut]
    page: int
    page_size: int
    total: int
    total_pages: int

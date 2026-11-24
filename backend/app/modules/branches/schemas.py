"""Request/response schemas for /branches (JSON uses camelCase)."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

BranchStatus = Literal["ACTIVE", "INACTIVE"]

# Codes like CN01, HN-CAU-GIAY, Q1_02
BRANCH_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
PHONE_PATTERN = r"^\+?[0-9][0-9 .-]{5,18}$"


class BranchIn(CamelModel):
    """Body of POST /branches and PUT /branches/{id} (PUT replaces every field below)."""

    branch_code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("branch_code", "name", "address", mode="before")
    @classmethod
    def strip_required(cls, v):
        # Strip first so "   " counts as missing (-> 422 like an absent field)
        return v.strip() if isinstance(v, str) else v

    @field_validator("branch_code")
    @classmethod
    def check_code(cls, v: str) -> str:
        if not re.fullmatch(BRANCH_CODE_PATTERN, v):
            raise ValueError("Only letters, digits, '-' and '_' (must start with a letter or digit)")
        return v.upper()

    @field_validator("phone", mode="before")
    @classmethod
    def check_phone(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Phone must be a string")
        v = v.strip()
        if not v:
            return None
        if not re.fullmatch(PHONE_PATTERN, v):
            raise ValueError("Invalid phone number")
        return v


class BranchStatusIn(CamelModel):
    status: BranchStatus


class BranchOut(CamelModel):
    id: int
    store_id: int
    branch_code: str
    name: str
    address: str
    phone: str | None
    status: str
    created_at: datetime


class BranchCreatedOut(BranchOut):
    inventory_rows_created: int  # inventory rows (quantity 0) created for the store's ACTIVE variants

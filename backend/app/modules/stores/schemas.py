"""Request/response schemas for /stores (JSON uses camelCase)."""
from datetime import datetime

from pydantic import Field, field_validator

from app.modules.branches.schemas import CamelModel


class StoreUpdate(CamelModel):
    name: str = Field(min_length=2, max_length=150)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class StoreOut(CamelModel):
    store_id: int
    name: str
    plan: str | None
    subscription_status: str | None
    subscription_expires_at: datetime | None
    created_at: datetime
    branch_count: int
    active_branch_count: int
    staff_count: int
    can_edit: bool

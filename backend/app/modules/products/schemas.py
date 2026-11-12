"""Request/response schemas for /products (JSON uses camelCase)."""
from datetime import datetime

from pydantic import Field, field_validator

from app.modules.auth.schemas import CamelModel


class ProductCreateIn(CamelModel):
    category_id: int = Field(gt=0)
    product_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("product_code", "name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Must not be blank")
        return v


class ProductOut(CamelModel):
    id: int
    store_id: int
    category_id: int
    product_code: str
    name: str
    description: str | None
    image_url: str | None
    status: str
    created_at: datetime
    created_by: int

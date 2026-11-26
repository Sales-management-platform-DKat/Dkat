"""Public catalog responses (FR-07.1 - FR-07.4).

These models are an ALLOWLIST: only the fields below ever leave the server (FR-07.5). Never add
cost price, stock quantities, reservations, product codes, store ids, statuses, created_by / created_at
or anything else internal. The detail page adds what the pre-order form needs: variant id + SKU and,
per ACTIVE branch, IN_STOCK / OUT_OF_STOCK (never the quantity).
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


class PublicCategoryRef(CamelModel):
    id: int
    name: str


class PublicProduct(CamelModel):
    id: int
    name: str
    image_url: str | None
    category: PublicCategoryRef
    price_min: float  # lowest price among ACTIVE variants
    price_max: float  # highest price among ACTIVE variants
    in_stock: bool  # some ACTIVE branch has available stock > 0 (never the quantity itself)


class PublicProductPage(CamelModel):
    items: list[PublicProduct]
    page: int
    size: int
    total: int
    total_pages: int


class PublicCategoryNode(CamelModel):
    id: int
    name: str
    children: list["PublicCategoryNode"]


class PublicAttributeValue(CamelModel):
    name: str
    value: str


class PublicBranchAvailability(CamelModel):
    branch_id: int  # an ACTIVE branch from GET /public/branches
    availability: Literal["IN_STOCK", "OUT_OF_STOCK"]


class PublicVariant(CamelModel):
    id: int  # the variantId the pre-order form submits
    sku: str
    name: str
    price: float
    attributes: list[PublicAttributeValue]
    branches: list[PublicBranchAvailability]  # one entry per ACTIVE branch of the store


class PublicProductDetail(CamelModel):
    id: int
    name: str
    description: str | None
    image_url: str | None
    category: PublicCategoryRef
    price_min: float
    price_max: float
    in_stock: bool
    variants: list[PublicVariant]  # ACTIVE variants only


class PublicBranch(CamelModel):
    branch_id: int
    name: str
    address: str
    phone: str | None

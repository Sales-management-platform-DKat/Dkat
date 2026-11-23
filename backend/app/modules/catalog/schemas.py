"""Public catalog responses (FR-07.1 - FR-07.3).

These models are an allowlist: only the fields below ever leave the server (FR-07.5).
Never add cost_price, stock quantities, reservations, product codes, store ids, statuses,
created_by/created_at or anything else internal. The detail page (FR-07.4) adds what the
pre-order form needs: variant id + SKU and branch id + IN_STOCK/OUT_OF_STOCK.
"""
from typing import Literal

from app.modules.auth.schemas import CamelModel


class PublicCategoryRef(CamelModel):
    id: int
    name: str


class PublicProductOut(CamelModel):
    id: int
    name: str
    image_url: str | None
    category: PublicCategoryRef
    price_min: float  # lowest price among ACTIVE variants
    price_max: float  # highest price among ACTIVE variants
    in_stock: bool  # some ACTIVE branch has available stock > 0 (never the quantity itself)


class PublicProductPageOut(CamelModel):
    items: list[PublicProductOut]
    page: int
    size: int
    total: int
    total_pages: int


class PublicCategoryNode(CamelModel):
    id: int
    name: str
    children: list["PublicCategoryNode"]


# ---- product detail page + pre-order form (FR-07.4)

Availability = Literal["IN_STOCK", "OUT_OF_STOCK"]


class PublicAttributeValue(CamelModel):
    name: str
    value: str


class PublicBranchAvailability(CamelModel):
    branch_id: int  # an ACTIVE branch from GET /public/branches
    availability: Availability  # available stock > 0 or not; the quantity itself is never returned


class PublicVariantOut(CamelModel):
    id: int  # the variantId the pre-order form submits
    sku: str
    name: str
    price: float
    attributes: list[PublicAttributeValue]
    branches: list[PublicBranchAvailability]  # one entry per ACTIVE branch of the store


class PublicProductDetailOut(CamelModel):
    id: int
    name: str
    description: str | None
    image_url: str | None
    category: PublicCategoryRef
    price_min: float
    price_max: float
    in_stock: bool
    variants: list[PublicVariantOut]  # ACTIVE variants only


class PublicBranchOut(CamelModel):
    id: int
    name: str
    address: str
    phone: str | None

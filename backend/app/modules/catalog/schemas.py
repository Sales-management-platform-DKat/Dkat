"""Public catalog responses (FR-07.1 - FR-07.3).

These models are an allowlist: only the fields below ever leave the server (FR-07.5).
Never add cost_price, stock quantities, reservations, SKU/product codes, store/branch ids,
created_by/created_at or anything else internal.
"""
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

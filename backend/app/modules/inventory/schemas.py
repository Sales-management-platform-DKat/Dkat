"""Response schemas for inventory (JSON uses camelCase)."""
from datetime import datetime

from app.modules.auth.schemas import CamelModel


class InventoryItemOut(CamelModel):
    branch_id: int
    variant_id: int
    sku: str
    variant_name: str
    product_id: int
    product_name: str
    quantity: int
    updated_at: datetime


class InventoryListOut(CamelModel):
    branch_ids: list[int]  # branches included in this result (after permission filtering)
    items: list[InventoryItemOut]

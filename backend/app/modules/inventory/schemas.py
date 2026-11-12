from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

InventoryId = Annotated[int, Field(gt=0, le=9223372036854775807)]


class InventoryItem(BaseModel):
    branchId: int
    branchName: str
    productId: int
    productName: str
    variantId: int
    variantName: str
    sku: str
    quantity: int
    reserved: int
    available: int
    updatedAt: datetime

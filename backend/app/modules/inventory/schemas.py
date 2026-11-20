from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

InventoryId = Annotated[int, Field(gt=0, le=9223372036854775807)]
MAX_STOCK_QUANTITY = 2147483647
ExportReason = Literal["HU_HONG", "MAU", "KHAC"]
StockMovementType = Literal["IMPORT", "EXPORT", "ADJUSTMENT"]


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


class StockLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variantId: InventoryId
    quantity: Annotated[int, Field(strict=True, gt=0, le=MAX_STOCK_QUANTITY)]


class StockImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branchId: InventoryId
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    items: list[StockLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_unique_variants(self):
        if len({item.variantId for item in self.items}) != len(self.items):
            raise ValueError("Each variant must appear only once")
        return self


class StockExportInput(StockImportInput):
    reason: ExportReason


class StockTakeLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variantId: InventoryId
    countedQuantity: Annotated[int, Field(strict=True, ge=0, le=MAX_STOCK_QUANTITY)]


class StockTakeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branchId: InventoryId
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    items: list[StockTakeLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_unique_variants(self):
        if len({item.variantId for item in self.items}) != len(self.items):
            raise ValueError("Each variant must appear only once")
        return self


class StockLineResult(BaseModel):
    variantId: int
    inventoryId: int
    movementId: int
    quantityBefore: int
    quantityChange: int
    quantityAfter: int


class StockChangeResult(BaseModel):
    branchId: int
    movementType: StockMovementType
    reason: ExportReason | None = None
    items: list[StockLineResult]

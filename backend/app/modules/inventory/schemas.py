from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.query_schemas import DatePageFilters

InventoryId = Annotated[int, Field(gt=0, le=9223372036854775807)]
MAX_STOCK_QUANTITY = 2147483647
ExportReason = Literal["HU_HONG", "MAU", "KHAC"]
StockMovementType = Literal["IMPORT", "EXPORT", "ADJUSTMENT"]
MovementType = Literal["IMPORT", "EXPORT", "ADJUSTMENT", "SALE", "PREORDER_FULFILLMENT"]


class MovementFilters(DatePageFilters):
    branchId: InventoryId | None = None
    variantId: InventoryId | None = None
    type: MovementType | None = None


class InventoryMovement(BaseModel):
    movementId: int
    inventoryId: int
    branchId: int
    branchName: str
    productId: int
    productName: str
    variantId: int
    variantName: str
    sku: str
    movementType: MovementType
    quantityChange: int
    createdBy: int
    createdByName: str | None
    note: str | None
    referenceType: str | None
    referenceId: int | None
    exportReason: ExportReason | None
    createdAt: datetime

    @field_validator("createdAt")
    @classmethod
    def add_utc_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


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


class StockVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variantId: InventoryId


class StockLineInput(StockVariantInput):
    quantity: Annotated[int, Field(strict=True, gt=0, le=MAX_STOCK_QUANTITY)]


class StocktakeLineInput(StockVariantInput):
    countedQuantity: Annotated[int, Field(strict=True, ge=0, le=MAX_STOCK_QUANTITY)]


StockLine = TypeVar("StockLine", bound=StockVariantInput)


class StockBatchInput(BaseModel, Generic[StockLine]):
    model_config = ConfigDict(extra="forbid")

    branchId: InventoryId
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    items: list[StockLine] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_unique_variants(self):
        if len({item.variantId for item in self.items}) != len(self.items):
            raise ValueError("Each variant must appear only once")
        return self


class StockImportInput(StockBatchInput[StockLineInput]):
    pass


class StockExportInput(StockImportInput):
    reason: ExportReason


class StocktakeInput(StockBatchInput[StocktakeLineInput]):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class StockLineResult(BaseModel):
    variantId: int
    inventoryId: int
    movementId: int | None
    quantityBefore: int
    quantityChange: int
    quantityAfter: int


class StockChangeResult(BaseModel):
    branchId: int
    movementType: StockMovementType
    reason: ExportReason | None = None
    items: list[StockLineResult]

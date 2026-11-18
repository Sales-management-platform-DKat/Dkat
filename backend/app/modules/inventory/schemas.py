from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

InventoryId = Annotated[int, Field(gt=0, le=9223372036854775807)]
MAX_STOCK_QUANTITY = 2147483647
ExportReason = Literal["HU_HONG", "MAU", "KHAC"]
StockMovementType = Literal["IMPORT", "EXPORT", "ADJUSTMENT"]
MovementType = Literal["IMPORT", "EXPORT", "ADJUSTMENT", "SALE", "PREORDER_FULFILLMENT"]


class MovementFilters(BaseModel):
    branchId: InventoryId | None = None
    variantId: InventoryId | None = None
    type: MovementType | None = None
    from_date: date | datetime | None = Field(default=None, alias="from")
    to_date: date | datetime | None = Field(default=None, alias="to")
    page: int = Field(default=1, ge=1, le=21474836)
    size: int = Field(default=50, ge=1, le=100)

    @field_validator("from_date", "to_date", mode="before")
    @classmethod
    def parse_date(cls, value):
        if not isinstance(value, str):
            return value
        try:
            if len(value) == 10:
                day = date.fromisoformat(value)
                if day.isoformat() == value:
                    return day
                raise ValueError
            if "T" not in value:
                raise ValueError
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Use YYYY-MM-DD or an ISO 8601 timestamp") from None

    @staticmethod
    def utc_bound(value: date | datetime | None, *, end: bool = False) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.astimezone(timezone.utc)
            return value.replace(tzinfo=None)
        # A calendar date is interpreted in Vietnam. The end covers the full day.
        day_start = datetime.combine(value, time.min)
        return day_start - timedelta(hours=7) + (timedelta(days=1) if end else timedelta())

    @property
    def end_exclusive(self) -> bool:
        return self.to_date is not None and not isinstance(self.to_date, datetime)

    @model_validator(mode="after")
    def validate_period(self):
        try:
            start = self.utc_bound(self.from_date)
            end = self.utc_bound(self.to_date, end=True)
        except (ValueError, OverflowError):
            raise ValueError("Date is outside the permitted range") from None
        if start is not None and end is not None and (start > end or (start == end and self.end_exclusive)):
            raise ValueError("from must be at or before to")
        if any(bound is not None and bound.year < 1000 for bound in (start, end)):
            raise ValueError("Date is outside the permitted range")
        return self


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

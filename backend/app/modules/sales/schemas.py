from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SalesId = Annotated[int, Field(gt=0, le=9223372036854775807)]
Discount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]


class SalesLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variantId: SalesId
    quantity: Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class SalesOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branchId: SalesId
    customerId: SalesId | None = None
    discountAmount: Discount = Decimal("0.00")
    items: list[SalesLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_unique_variants(self):
        if len({item.variantId for item in self.items}) != len(self.items):
            raise ValueError("Each variant must appear only once")
        return self


class SalesOrderLine(BaseModel):
    variantId: int
    productName: str
    sku: str
    unitPrice: Decimal
    quantity: int
    lineTotal: Decimal


class PendingSalesOrder(BaseModel):
    salesOrderId: int
    orderCode: str
    branchId: int
    customerId: int | None
    status: Literal["PENDING"] = "PENDING"
    subtotal: Decimal
    discountAmount: Decimal
    totalAmount: Decimal
    items: list[SalesOrderLine]

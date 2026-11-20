from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

PositiveId = Annotated[int, Field(gt=0, le=9223372036854775807)]
Quantity = Annotated[int, Field(strict=True, gt=0, le=2147483647)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]


class SalesOrderLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variantId: PositiveId
    quantity: Quantity


class SalesOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branchId: PositiveId
    customerId: PositiveId | None = None
    items: list[SalesOrderLineInput] = Field(min_length=1, max_length=100)
    discountAmount: Money = Decimal("0")


class ConfirmPaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paymentMethod: Literal["CASH", "BANK_TRANSFER", "CARD", "OTHER"]
    amountTendered: Money | None = None


class RefundInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, Field(min_length=3, max_length=255)]


class SalesOrderItem(BaseModel):
    variantId: int
    productName: str
    sku: str
    unitPrice: Decimal
    quantity: int
    lineTotal: Decimal


class SalesOrderRecord(BaseModel):
    salesOrderId: int
    orderCode: str
    branchId: int
    customerId: int | None = None
    customerName: str = "Guest"
    subtotal: Decimal
    discountAmount: Decimal
    totalAmount: Decimal
    status: str
    items: list[SalesOrderItem]

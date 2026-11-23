from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.query_schemas import DatePageFilters

SalesId = Annotated[int, Field(gt=0, le=9223372036854775807)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
OrderStatus = Literal["PENDING", "PAID", "CANCELLED"]
PaymentMethod = Literal["CASH", "BANK_TRANSFER", "CARD", "OTHER"]


class ConfirmPaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paymentMethod: PaymentMethod
    amount: Money


class SalesOrderFilters(DatePageFilters):
    branchId: SalesId | None = None
    status: OrderStatus | None = None
    keyword: str | None = Field(default=None, max_length=200)
    customerId: SalesId | None = None


class CancelOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class SalesOrderSummary(BaseModel):
    salesOrderId: int
    orderCode: str
    branchId: int
    branchName: str
    customerId: int | None
    customerName: str | None
    createdBy: int
    createdByName: str | None
    subtotal: Decimal
    discountAmount: Decimal
    totalAmount: Decimal
    status: OrderStatus
    createdAt: datetime
    paidAt: datetime | None
    cancelledAt: datetime | None
    cancelReason: str | None
    paymentMethods: list[str] = Field(default_factory=list)

    @field_validator("createdAt", "paidAt", "cancelledAt")
    @classmethod
    def utc_time(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class OrderPayment(BaseModel):
    paymentId: int
    paymentMethod: PaymentMethod
    amount: Decimal
    status: Literal["PENDING", "SUCCESS", "FAILED", "REFUNDED"]
    confirmedBy: int
    confirmedAt: datetime | None

    @field_validator("confirmedAt")
    @classmethod
    def utc_time(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class SalesLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variantId: SalesId
    quantity: Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class SalesOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branchId: SalesId
    customerId: SalesId | None = None
    discountAmount: Money = Decimal("0.00")
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


class SalesOrderDetail(SalesOrderSummary):
    items: list[SalesOrderLine]
    payments: list[OrderPayment]

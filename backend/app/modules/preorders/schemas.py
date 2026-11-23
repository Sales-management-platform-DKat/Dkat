from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.modules.customers.service import normalize_phone

PreorderId = Annotated[int, Field(strict=True, gt=0, le=9223372036854775807)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class PreorderCustomer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fullName: Name
    phone: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    email: Annotated[str, StringConstraints(max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")] | None = None
    address: Address

    @field_validator("phone")
    @classmethod
    def canonical_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def optional_email(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value


class PreorderLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variantId: PreorderId
    quantity: Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class PreorderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branchId: PreorderId
    customer: PreorderCustomer
    items: list[PreorderLineInput] = Field(min_length=1, max_length=100)
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None

    @model_validator(mode="after")
    def unique_variants(self):
        if len({item.variantId for item in self.items}) != len(self.items):
            raise ValueError("Mỗi biến thể chỉ được xuất hiện một lần")
        return self


class PreorderLine(BaseModel):
    variantId: int
    productName: str
    sku: str
    unitPrice: Decimal
    quantity: int
    allocatedQuantity: int = 0
    lineTotal: Decimal


class CreatedPreorder(BaseModel):
    preorderId: int
    preorderCode: str
    branchId: int
    customerId: int
    customer: PreorderCustomer
    totalAmount: Decimal
    status: Literal["WAITING_STOCK"] = "WAITING_STOCK"
    paymentStatus: Literal["UNPAID"] = "UNPAID"
    note: str | None
    items: list[PreorderLine]
    createdAt: datetime


class PreorderIssue(BaseModel):
    field: str
    reason: str


class PreorderErrorBody(BaseModel):
    code: str
    message: str
    details: list[PreorderIssue] = Field(default_factory=list)

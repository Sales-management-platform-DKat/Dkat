from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from app.modules.products.schemas import AttributeDataType, ProductId, ProductStatus

AttributeText = Annotated[str, StringConstraints(max_length=255)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
Sku = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class AttributeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    dataType: AttributeDataType


class AttributeRecord(AttributeInput):
    attributeId: int
    status: ProductStatus


class AttributeValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attributeId: ProductId
    value: AttributeText | StrictBool | Decimal


class VariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: Sku | None = None
    variantName: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    price: Money
    costPrice: Money | None = None
    barcode: str | None = Field(default=None, max_length=100)
    attributes: list[AttributeValueInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_attributes(self):
        if len({item.attributeId for item in self.attributes}) != len(self.attributes):
            raise ValueError("Each attribute can appear only once per variant")
        return self


class VariantCreate(VariantInput):
    sku: Sku

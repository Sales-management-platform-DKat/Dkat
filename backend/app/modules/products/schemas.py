from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ProductVariant(BaseModel):
    variant_id: int
    sku: str
    variant_name: str
    price: Decimal


class Product(BaseModel):
    product_id: int
    category_id: int
    product_code: str
    name: str
    variants: list[ProductVariant]


ProductId = Annotated[int, Field(gt=0, le=9223372036854775807)]
ProductStatus = Literal["ACTIVE", "INACTIVE"]
ProductSort = Literal["id", "-id", "name", "-name", "createdAt", "-createdAt"]
AttributeDataType = Literal["TEXT", "NUMBER", "BOOLEAN"]


class VariantAttribute(BaseModel):
    attribute_id: int
    name: str
    data_type: AttributeDataType
    value: str


class VariantDetail(ProductVariant):
    barcode: str | None
    cost_price: Decimal | None
    status: ProductStatus
    attributes: list[VariantAttribute] = Field(default_factory=list)


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categoryId: ProductId
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: str | None = Field(default=None, max_length=16000)
    imageUrl: str | None = Field(default=None, max_length=500)


class ProductCreate(ProductInput):
    productCode: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None = None


class ProductStatusInput(BaseModel):
    status: ProductStatus


class ProductRecord(ProductInput):
    productId: int
    productCode: str
    status: ProductStatus
    createdBy: int


class ProductDetail(ProductRecord):
    variants: list[VariantDetail]

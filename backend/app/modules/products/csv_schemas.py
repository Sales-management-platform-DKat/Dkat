from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.core.csv import CsvIssue
from app.modules.products.variant_schemas import Money, Sku


class CsvProductRow(BaseModel):
    product_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    variant_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    sku: Sku
    price: Money
    cost_price: Money | None = None
    attributes: str = ""


class ImportCounts(BaseModel):
    categories: int = 0
    products: int = 0
    variants: int = 0
    attributes: int = 0


class ImportedCsvRow(BaseModel):
    line: int
    productId: int
    variantId: int
    sku: str


class CsvImportResult(BaseModel):
    dryRun: bool
    valid: bool
    totalRows: int
    validRows: int
    summary: ImportCounts | None = None
    errors: list[CsvIssue]
    rows: list[ImportedCsvRow]

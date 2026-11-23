from collections import defaultdict
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import text
from sqlalchemy.engine import Connection, Row

from app.core.csv import CsvIssue, issue, read_csv
from app.core.permissions import Actor, require_branch_access
from app.db.collation import column_collation
from app.modules.inventory.schemas import (
    MAX_STOCK_NOTE_LENGTH, MAX_STOCK_QUANTITY, StockImportInput, StockLineInput, StockLineResult, StockNote,
)
from app.modules.inventory.service import change_stock
from app.modules.products.variant_schemas import Sku

MAX_ROWS = 1000
COLUMNS = ("sku", "quantity", "note")
SKU_LOOKUP_BATCH_SIZE = 100


class CsvStockFields(BaseModel):
    sku: Sku
    quantity: Annotated[int, Field(gt=0, le=MAX_STOCK_QUANTITY)]
    note: StockNote | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_integer(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not (value.isascii() and value.isdecimal()):
                raise ValueError("Số lượng phải là số nguyên dương")
            return value.lstrip("0") or "0"
        return value


class CsvStockRow(CsvStockFields):
    line: int
    variantId: int


class CsvStockImportResult(BaseModel):
    dryRun: bool
    valid: bool
    totalRows: int
    validRows: int
    rows: list[CsvStockRow]
    errors: list[CsvIssue]
    items: list[StockLineResult] = Field(default_factory=list)


class CsvStockBatch(StockImportInput):
    items: list[StockLineInput] = Field(min_length=1, max_length=MAX_ROWS)


def resolve_skus(db: Connection, store_id: int, branch_id: int, skus: list[str]) -> dict[str, Row]:
    values = list(dict.fromkeys(skus))
    if not values:
        return {}
    collation = column_collation(db, "product_variants", "sku")
    found = {}
    for start in range(0, len(values), SKU_LOOKUP_BATCH_SIZE):
        batch = values[start:start + SKU_LOOKUP_BATCH_SIZE]
        params = {f"sku{index}": sku for index, sku in enumerate(batch)}
        # Return each input's match using the same comparison rules as the SKU column.
        source = " UNION ALL ".join(f"SELECT {index} AS row_no, :sku{index} AS input_sku" for index in range(len(batch)))
        matches = db.execute(text(f"""
            SELECT csv_rows.row_no, v.variant_id, v.sku, COALESCE(i.quantity, 0) AS on_hand
            FROM ({source}) AS csv_rows
            JOIN product_variants AS v ON v.sku = csv_rows.input_sku COLLATE {collation}
            JOIN products AS p ON p.product_id=v.product_id AND p.store_id=:store
            LEFT JOIN inventory AS i ON i.branch_id=:branch AND i.variant_id=v.variant_id
        """), {**params, "store": store_id, "branch": branch_id})
        found.update((batch[row.row_no], row) for row in matches)
    return found


def stock_limit_issues(rows: list[CsvStockRow]) -> list[CsvIssue]:
    return [issue(row.line, "quantity", "STOCK_LIMIT_EXCEEDED", "Tổng tồn sau nhập vượt giới hạn cho SKU này") for row in rows]


def import_stock_csv(
    db: Connection, actor: Actor, branch_id: int, content: bytes, dry_run: bool,
) -> CsvStockImportResult:
    require_branch_access(db, actor, branch_id)
    records, errors, total = read_csv(content, COLUMNS, MAX_ROWS)
    parsed = []
    for record in records:
        try:
            parsed.append((record.line, CsvStockFields.model_validate(record.values)))
        except ValidationError as exc:
            errors.extend(issue(record.line, str(error["loc"][0]), "INVALID_VALUE", error["msg"]) for error in exc.errors())

    resolved = resolve_skus(db, actor.store_id, branch_id, [row.sku for _, row in parsed])
    groups: dict[int, list[CsvStockRow]] = defaultdict(list)
    on_hand = {}
    for line, row in parsed:
        match = resolved.get(row.sku)
        if match is None:
            errors.append(issue(line, "sku", "SKU_NOT_FOUND", "SKU không tồn tại trong cửa hàng"))
            continue
        groups[match.variant_id].append(CsvStockRow(
            line=line, variantId=match.variant_id, sku=match.sku, quantity=row.quantity, note=row.note or None,
        ))
        on_hand[match.variant_id] = match.on_hand

    valid_rows, items, notes = [], [], {}
    for variant_id, rows in groups.items():
        quantity = sum(row.quantity for row in rows)
        if on_hand[variant_id] + quantity > MAX_STOCK_QUANTITY:
            errors.extend(stock_limit_issues(rows))
            continue
        valid_rows.extend(rows)
        items.append(StockLineInput(variantId=variant_id, quantity=quantity))
        note = " | ".join(dict.fromkeys(row.note for row in rows if row.note))
        notes[variant_id] = note[:MAX_STOCK_NOTE_LENGTH] or None

    valid_rows.sort(key=lambda row: row.line)
    errors.sort(key=lambda error: (error.line, error.field, error.code))
    result = CsvStockImportResult(
        dryRun=dry_run, valid=not errors, totalRows=total, validRows=len(valid_rows), rows=valid_rows, errors=errors,
    )
    if dry_run:
        return result
    if errors:
        raise HTTPException(422, {"code": "INVALID_STOCK_CSV", **result.model_dump(mode="json")})

    try:
        changed = change_stock(db, actor, CsvStockBatch(branchId=branch_id, items=items), notes_by_variant=notes)
    except HTTPException as exc:
        if exc.status_code != 409 or not isinstance(exc.detail, dict) or exc.detail.get("code") != "STOCK_LIMIT_EXCEEDED":
            raise
        # Another receipt can raise the on-hand quantity after validation. The locked check wins.
        variant_id = exc.detail["variantId"]
        result.valid = False
        result.errors = stock_limit_issues(groups[variant_id])
        result.rows = [row for row in result.rows if row.variantId != variant_id]
        result.validRows = len(result.rows)
        raise HTTPException(422, {"code": "INVALID_STOCK_CSV", **result.model_dump(mode="json")}) from None
    result.items = changed.items
    return result

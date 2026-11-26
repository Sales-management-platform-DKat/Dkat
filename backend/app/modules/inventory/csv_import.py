import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import text
from sqlalchemy.engine import Connection, Row

from app.core.csv import CsvIssue, issue
from app.core.permissions import Actor, require_branch_access
from app.core.spreadsheet import read_table
from app.db.collation import column_collation
from app.modules.inventory.schemas import (
    MAX_STOCK_NOTE_LENGTH, MAX_STOCK_QUANTITY, StockImportInput, StockLineInput, StockLineResult, StockNote,
)
from app.modules.inventory.service import change_stock
from app.modules.products.variant_schemas import Sku

MAX_ROWS = 1000
REQUIRED_COLUMNS = ("sku", "quantity")
OPTIONAL_COLUMNS = ("note",)
COLUMN_ALIASES = {
    "mã sku": "sku", "ma sku": "sku", "mã hàng": "sku", "sku biến thể": "sku",
    "số lượng": "quantity", "so luong": "quantity", "qty": "quantity", "số lượng nhập": "quantity",
    "ghi chú": "note", "ghi chu": "note", "notes": "note",
}
SKU_LOOKUP_BATCH_SIZE = 100
FILE_REFERENCE = "STOCK_FILE"
DUPLICATE_WINDOW = timedelta(hours=24)


class CsvStockFields(BaseModel):
    sku: Sku
    quantity: Annotated[int, Field(gt=0, le=MAX_STOCK_QUANTITY)]
    note: StockNote | None = None

    @field_validator("sku", mode="before")
    @classmethod
    def require_sku(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("Thiếu SKU")
        return value

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_integer(cls, value):
        if isinstance(value, str):
            value = value.strip().replace(" ", "")
            if not value:
                raise ValueError("Thiếu số lượng")
            if value.startswith("-"):
                raise ValueError("Số lượng không được âm")
            if not (value.isascii() and value.isdecimal()):
                raise ValueError("Số lượng phải là số nguyên dương")
            value = value.lstrip("0") or "0"
            if value == "0":
                raise ValueError("Số lượng phải lớn hơn 0")
        return value


class CsvStockRow(CsvStockFields):
    line: int
    variantId: int
    productName: str | None = None
    variantName: str | None = None
    quantityBefore: int | None = None


class CsvStockImportResult(BaseModel):
    dryRun: bool
    valid: bool
    totalRows: int
    validRows: int
    rows: list[CsvStockRow]
    errors: list[CsvIssue]
    warnings: list[CsvIssue] = Field(default_factory=list)
    fileType: str = "csv"
    duplicateOfImportAt: datetime | None = None
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
            SELECT csv_rows.row_no, v.variant_id, v.sku, v.variant_name, v.status AS variant_status,
                   p.name AS product_name, p.status AS product_status, COALESCE(i.quantity, 0) AS on_hand
            FROM ({source}) AS csv_rows
            JOIN product_variants AS v ON v.sku = csv_rows.input_sku COLLATE {collation}
            JOIN products AS p ON p.product_id=v.product_id AND p.store_id=:store
            LEFT JOIN inventory AS i ON i.branch_id=:branch AND i.variant_id=v.variant_id
        """), {**params, "store": store_id, "branch": branch_id})
        found.update((batch[row.row_no], row) for row in matches)
    return found


def stock_limit_issues(rows: list[CsvStockRow]) -> list[CsvIssue]:
    return [issue(row.line, "quantity", "STOCK_LIMIT_EXCEEDED", "Tổng tồn sau nhập vượt giới hạn cho SKU này") for row in rows]


def file_fingerprint(branch_id: int, items: list[StockLineInput]) -> int:
    """Same branch + same variant quantities => same fingerprint, however the file was saved."""
    canonical = f"{branch_id}|" + ";".join(f"{item.variantId}:{item.quantity}" for item in sorted(items, key=lambda x: x.variantId))
    # 60 bits fit in a signed BIGINT reference_id.
    return int(hashlib.sha256(canonical.encode()).hexdigest()[:15], 16)


def previous_identical_import(db: Connection, branch_id: int, fingerprint: int) -> datetime | None:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - DUPLICATE_WINDOW
    value = db.execute(text("""
        SELECT MAX(m.created_at) FROM inventory_movements AS m
        JOIN inventory AS i ON i.inventory_id = m.inventory_id
        WHERE i.branch_id = :branch AND m.reference_type = :ref_type AND m.reference_id = :ref_id
          AND m.created_at >= :since
    """), {"branch": branch_id, "ref_type": FILE_REFERENCE, "ref_id": fingerprint, "since": since}).scalar()
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def import_stock_csv(
    db: Connection, actor: Actor, branch_id: int, content: bytes, dry_run: bool,
    filename: str | None = None, allow_duplicate: bool = False,
) -> CsvStockImportResult:
    require_branch_access(db, actor, branch_id)
    records, errors, total, kind = read_table(
        content, filename, required=REQUIRED_COLUMNS, optional=OPTIONAL_COLUMNS,
        aliases=COLUMN_ALIASES, max_rows=MAX_ROWS,
    )
    parsed = []
    for record in records:
        try:
            parsed.append((record.line, CsvStockFields.model_validate(record.values)))
        except ValidationError as exc:
            for error in exc.errors():
                message = str(error["msg"]).removeprefix("Value error, ")
                if error["type"] in {"string_too_long", "less_than_equal"}:
                    message = "Giá trị quá lớn"
                errors.append(issue(record.line, str(error["loc"][0]), "INVALID_VALUE", message))

    resolved = resolve_skus(db, actor.store_id, branch_id, [row.sku for _, row in parsed])
    groups: dict[int, list[CsvStockRow]] = defaultdict(list)
    on_hand = {}
    warnings: list[CsvIssue] = []
    for line, row in parsed:
        match = resolved.get(row.sku)
        if match is None:
            errors.append(issue(line, "sku", "SKU_NOT_FOUND", f"SKU \"{row.sku}\" không tồn tại trong cửa hàng"))
            continue
        if match.variant_status != "ACTIVE" or match.product_status != "ACTIVE":
            errors.append(issue(line, "sku", "SKU_INACTIVE", f"SKU \"{match.sku}\" đang ngừng kinh doanh"))
            continue
        if groups[match.variant_id]:
            first = groups[match.variant_id][0].line
            warnings.append(issue(line, "sku", "DUPLICATE_SKU_ROW",
                                  f"SKU \"{match.sku}\" đã có ở dòng {first}; số lượng sẽ được cộng dồn"))
        groups[match.variant_id].append(CsvStockRow(
            line=line, variantId=match.variant_id, sku=match.sku, quantity=row.quantity, note=row.note or None,
            productName=match.product_name, variantName=match.variant_name, quantityBefore=int(match.on_hand),
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
    warnings.sort(key=lambda warning: warning.line)
    fingerprint = file_fingerprint(branch_id, items) if items else None
    duplicate_at = previous_identical_import(db, branch_id, fingerprint) if fingerprint is not None else None
    result = CsvStockImportResult(
        dryRun=dry_run, valid=not errors, totalRows=total, validRows=len(valid_rows), rows=valid_rows,
        errors=errors, warnings=warnings, fileType=kind, duplicateOfImportAt=duplicate_at,
    )
    if dry_run:
        return result
    if errors:
        raise HTTPException(422, {"code": "INVALID_STOCK_CSV", **result.model_dump(mode="json")})
    if duplicate_at is not None and not allow_duplicate:
        raise HTTPException(409, {
            "code": "DUPLICATE_STOCK_IMPORT",
            "message": "Dữ liệu này đã được nhập vào chi nhánh trong 24 giờ qua. Xác nhận lại nếu đây là lô hàng mới.",
            "importedAt": duplicate_at.isoformat(),
        })

    try:
        changed = change_stock(
            db, actor, CsvStockBatch(branchId=branch_id, items=items), notes_by_variant=notes,
            reference=(FILE_REFERENCE, fingerprint),
        )
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

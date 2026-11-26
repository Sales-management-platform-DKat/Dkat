import hashlib
import re
from types import SimpleNamespace
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import bindparam, text
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
# The product columns are only needed for SKUs that do not exist yet.
OPTIONAL_COLUMNS = ("note", "product_name", "variant_name", "category", "price")
COLUMN_ALIASES = {
    "mã sku": "sku", "ma sku": "sku", "mã hàng": "sku", "sku biến thể": "sku",
    "số lượng": "quantity", "so luong": "quantity", "qty": "quantity", "số lượng nhập": "quantity",
    "ghi chú": "note", "ghi chu": "note", "notes": "note",
    "tên sản phẩm": "product_name", "ten san pham": "product_name", "sản phẩm": "product_name", "product": "product_name",
    "tên biến thể": "variant_name", "biến thể": "variant_name", "variant": "variant_name",
    "danh mục": "category", "category name": "category",
    "giá bán": "price", "gia ban": "price", "giá": "price", "đơn giá": "price",
}
SKU_LOOKUP_BATCH_SIZE = 100
FILE_REFERENCE = "STOCK_FILE"
DUPLICATE_WINDOW = timedelta(hours=24)
DEFAULT_CATEGORY = "Chưa phân loại"
MAX_PRICE = Decimal("9999999999.99")


class CsvStockFields(BaseModel):
    sku: Sku
    quantity: Annotated[int, Field(gt=0, le=MAX_STOCK_QUANTITY)]
    note: StockNote | None = None
    product_name: Annotated[str, Field(max_length=200)] | None = None
    variant_name: Annotated[str, Field(max_length=200)] | None = None
    category: Annotated[str, Field(max_length=100)] | None = None
    price: Decimal | None = None

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

    @field_validator("product_name", "variant_name", "category", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        text_value = str(value).strip().replace(" ", "").replace("₫", "").replace("đ", "")
        # "350.000" / "1.250.000" are Vietnamese thousand separators.
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", text_value):
            text_value = text_value.replace(".", "")
        try:
            price = Decimal(text_value)
        except InvalidOperation:
            raise ValueError("Giá bán phải là số") from None
        if price < 0 or price > MAX_PRICE or not price.is_finite():
            raise ValueError("Giá bán không hợp lệ")
        return price.quantize(Decimal("0.01"))


class CsvStockRow(BaseModel):
    line: int
    sku: str
    quantity: int
    note: str | None = None
    # EXISTING: SKU already in the store, stock is added. NEW: product/variant is created first.
    status: Literal["EXISTING", "NEW"] = "EXISTING"
    variantId: int | None = None
    productName: str | None = None
    variantName: str | None = None
    category: str | None = None
    price: Decimal | None = None
    quantityBefore: int | None = None


class CreatedVariant(BaseModel):
    sku: str
    productId: int
    variantId: int
    productName: str
    variantName: str
    category: str
    price: Decimal


class CsvStockImportResult(BaseModel):
    dryRun: bool
    valid: bool
    totalRows: int
    validRows: int
    newSkus: int = 0
    existingSkus: int = 0
    rows: list[CsvStockRow]
    errors: list[CsvIssue]
    warnings: list[CsvIssue] = Field(default_factory=list)
    fileType: str = "csv"
    duplicateOfImportAt: datetime | None = None
    created: list[CreatedVariant] = Field(default_factory=list)
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


def skus_used_elsewhere(db: Connection, skus: list[str]) -> set[str]:
    """SKUs are unique platform-wide; report clashes without revealing the other store."""
    if not skus:
        return set()
    rows = db.execute(
        text("SELECT LOWER(sku) FROM product_variants WHERE LOWER(sku) IN :skus")
        .bindparams(bindparam("skus", expanding=True)),
        {"skus": [sku.casefold() for sku in skus]},
    ).scalars()
    return set(rows)


def store_categories(db: Connection, store_id: int) -> dict[str, Row]:
    rows = db.execute(
        text("SELECT category_id, name, status FROM categories WHERE store_id = :store"), {"store": store_id},
    )
    by_name: dict[str, Row] = {}
    for row in rows:
        by_name.setdefault(row.name.strip().casefold(), row)
    return by_name


def stock_limit_issues(rows: list[CsvStockRow]) -> list[CsvIssue]:
    return [issue(row.line, "quantity", "STOCK_LIMIT_EXCEEDED", "Tổng tồn sau nhập vượt giới hạn cho SKU này") for row in rows]


def file_fingerprint(branch_id: int, totals: dict[str, int]) -> int:
    """Same branch + same SKU quantities => same fingerprint, however the file was saved."""
    canonical = f"{branch_id}|" + ";".join(f"{sku}:{quantity}" for sku, quantity in sorted(totals.items()))
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


def create_new_skus(db: Connection, actor: Actor, rows_by_sku: dict[str, list[CsvStockRow]]) -> list[CreatedVariant]:
    """Create the products/variants for NEW rows inside the import transaction."""
    from app.modules.products import service as product_service
    from app.modules.products.catalog_transaction import CatalogConflict, CatalogInvalid, CatalogNotFound
    from app.modules.products.category_schemas import CategoryInput
    from app.modules.products.category_service import save_category
    from app.modules.products.schemas import ProductCreate
    from app.modules.products.variant_schemas import VariantInput
    from app.modules.products.variant_service import save_variant

    categories = store_categories(db, actor.store_id)
    products: dict[tuple[str, str], int] = {}
    created = []
    try:
        for rows in rows_by_sku.values():
            first = rows[0]
            category_name = first.category or DEFAULT_CATEGORY
            category = categories.get(category_name.casefold())
            if category is None:
                saved = save_category(db, actor.store_id, CategoryInput(name=category_name))
                category = categories[category_name.casefold()] = SimpleNamespace(
                    category_id=saved.categoryId, name=saved.name, status=saved.status,
                )
            key = (first.productName.casefold(), category_name.casefold())
            if key not in products:
                # A new SKU becomes a variant of the store's product with the same name and category.
                same = db.execute(text("""
                    SELECT product_id FROM products
                    WHERE store_id = :store AND category_id = :category AND LOWER(name) = :name AND status = 'ACTIVE'
                    ORDER BY product_id LIMIT 1
                """), {"store": actor.store_id, "category": category.category_id, "name": first.productName.casefold()}).scalar()
                if same is not None:
                    products[key] = same
            if key not in products:
                record = product_service.create_product(db, actor.store_id, actor.user_id, ProductCreate(
                    categoryId=category.category_id, name=first.productName,
                ))
                products[key] = record.productId
            variant = save_variant(db, actor.store_id, VariantInput(
                sku=first.sku, variantName=first.variantName, price=first.price,
            ), product_id=products[key])
            created.append(CreatedVariant(
                sku=variant.sku, productId=products[key], variantId=variant.variant_id, productName=first.productName,
                variantName=variant.variant_name, category=category.name, price=variant.price,
            ))
    except CatalogConflict as error:
        raise HTTPException(409, str(error)) from None
    except (CatalogNotFound, CatalogInvalid) as error:
        raise HTTPException(422, str(error)) from None
    return created


def import_stock_csv(
    db: Connection, actor: Actor, branch_id: int, content: bytes, dry_run: bool,
    filename: str | None = None, allow_duplicate: bool = False,
) -> CsvStockImportResult:
    require_branch_access(db, actor, branch_id)
    can_create = actor.role in {"OWNER", "MANAGER"}
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
    unknown = [row.sku for _, row in parsed if row.sku not in resolved]
    taken_elsewhere = skus_used_elsewhere(db, unknown)
    categories = store_categories(db, actor.store_id)
    existing: dict[int, list[CsvStockRow]] = defaultdict(list)
    new: dict[str, list[CsvStockRow]] = defaultdict(list)
    on_hand = {}
    warnings: list[CsvIssue] = []
    for line, row in parsed:
        match = resolved.get(row.sku)
        if match is not None:
            if match.variant_status != "ACTIVE" or match.product_status != "ACTIVE":
                errors.append(issue(line, "sku", "SKU_INACTIVE", f"SKU \"{match.sku}\" đang ngừng kinh doanh"))
                continue
            if existing[match.variant_id]:
                first = existing[match.variant_id][0].line
                warnings.append(issue(line, "sku", "DUPLICATE_SKU_ROW",
                                      f"SKU \"{match.sku}\" đã có ở dòng {first}; số lượng sẽ được cộng dồn"))
            existing[match.variant_id].append(CsvStockRow(
                line=line, sku=match.sku, quantity=row.quantity, note=row.note or None, status="EXISTING",
                variantId=match.variant_id, productName=match.product_name, variantName=match.variant_name,
                quantityBefore=int(match.on_hand),
            ))
            on_hand[match.variant_id] = match.on_hand
            continue

        # Unknown SKU: create it when the row carries the product details.
        key = row.sku.casefold()
        if not can_create:
            errors.append(issue(line, "sku", "SKU_NOT_FOUND",
                                f"SKU \"{row.sku}\" chưa có trong cửa hàng; chỉ chủ cửa hàng hoặc quản lý được tạo sản phẩm mới"))
            continue
        missing = [label for label, value in (("product_name", row.product_name), ("price", row.price)) if value is None]
        if missing:
            errors.append(issue(line, "sku", "SKU_NOT_FOUND",
                                f"SKU \"{row.sku}\" chưa có trong cửa hàng. Điền cột {' và '.join(missing)} để tạo sản phẩm mới"))
            continue
        # Only reached when the user really tries to create it: SKUs are unique platform-wide.
        if key in taken_elsewhere:
            errors.append(issue(line, "sku", "SKU_TAKEN", f"SKU \"{row.sku}\" đã được sử dụng, hãy chọn SKU khác"))
            continue
        category_name = row.category or DEFAULT_CATEGORY
        category = categories.get(category_name.casefold())
        if category is not None and category.status != "ACTIVE":
            errors.append(issue(line, "category", "CATEGORY_INACTIVE", f"Danh mục \"{category.name}\" đang ngừng hoạt động"))
            continue
        candidate = CsvStockRow(
            line=line, sku=row.sku, quantity=row.quantity, note=row.note or None, status="NEW",
            productName=row.product_name, variantName=row.variant_name or "Mặc định",
            category=category.name if category else category_name, price=row.price, quantityBefore=0,
        )
        if new[key]:
            first = new[key][0]
            if (first.productName.casefold(), first.price, (first.category or "").casefold()) != (
                    candidate.productName.casefold(), candidate.price, (candidate.category or "").casefold()):
                errors.append(issue(line, "sku", "SKU_CONFLICT",
                                    f"SKU \"{row.sku}\" ở dòng {first.line} có tên, giá hoặc danh mục khác"))
                continue
            warnings.append(issue(line, "sku", "DUPLICATE_SKU_ROW",
                                  f"SKU \"{row.sku}\" đã có ở dòng {first.line}; số lượng sẽ được cộng dồn"))
        new[key].append(candidate)

    valid_rows, items, notes, totals = [], [], {}, {}
    for variant_id, rows in existing.items():
        quantity = sum(row.quantity for row in rows)
        if on_hand[variant_id] + quantity > MAX_STOCK_QUANTITY:
            errors.extend(stock_limit_issues(rows))
            continue
        valid_rows.extend(rows)
        items.append(StockLineInput(variantId=variant_id, quantity=quantity))
        note = " | ".join(dict.fromkeys(row.note for row in rows if row.note))
        notes[variant_id] = note[:MAX_STOCK_NOTE_LENGTH] or None
        totals[rows[0].sku.casefold()] = quantity
    for key, rows in new.items():
        valid_rows.extend(rows)
        totals[key] = sum(row.quantity for row in rows)

    valid_rows.sort(key=lambda row: row.line)
    errors.sort(key=lambda error: (error.line, error.field, error.code))
    warnings.sort(key=lambda warning: warning.line)
    fingerprint = file_fingerprint(branch_id, totals) if totals else None
    duplicate_at = previous_identical_import(db, branch_id, fingerprint) if fingerprint is not None else None
    result = CsvStockImportResult(
        dryRun=dry_run, valid=not errors, totalRows=total, validRows=len(valid_rows),
        newSkus=len(new), existingSkus=len(existing), rows=valid_rows,
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

    created = create_new_skus(db, actor, new) if new else []
    for variant in created:
        rows = new[variant.sku.casefold()]
        for row in rows:
            row.variantId = variant.variantId
        items.append(StockLineInput(variantId=variant.variantId, quantity=sum(row.quantity for row in rows)))
        note = " | ".join(dict.fromkeys(row.note for row in rows if row.note))
        notes[variant.variantId] = (f"SKU mới: {note}" if note else "SKU mới tạo khi nhập kho")[:MAX_STOCK_NOTE_LENGTH]

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
        result.errors = stock_limit_issues(existing.get(variant_id, []))
        result.rows = [row for row in result.rows if row.variantId != variant_id]
        result.validRows = len(result.rows)
        raise HTTPException(422, {"code": "INVALID_STOCK_CSV", **result.model_dump(mode="json")}) from None
    result.created = created
    result.items = changed.items
    return result

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import config
from app.core.csv import MAX_FILE_BYTES
from app.core.permissions import Actor, get_accessible_branch_ids, require_auth, require_branch_access
from app.db.session import engine, get_db
from app.modules.inventory.csv_import import CsvStockImportResult, import_stock_csv
from app.modules.inventory.post_import import process_committed_stock_import
from app.modules.inventory.schemas import (
    InventoryId, InventoryItem, InventoryMovement, MovementFilters,
    StockChangeResult, StockExportInput, StockImportInput, StocktakeInput,
)
from app.modules.inventory.service import change_stock, list_inventory, list_inventory_movements

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory", tags=["inventory"])
Reader = Annotated[Actor, Depends(require_auth)]
Database = Annotated[Session, Depends(get_db)]


def require_stock_writer(actor: Reader) -> Actor:
    if actor.role == "EMPLOYEE" and not config.ALLOW_EMPLOYEE_STOCK:
        raise HTTPException(403, "Bạn không có quyền thay đổi tồn kho.")
    return actor


StockWriter = Annotated[Actor, Depends(require_stock_writer)]


def record_stock_change(actor: Actor, data: StockImportInput | StocktakeInput) -> StockChangeResult:
    try:
        # Read the latest reservation totals after acquiring the inventory locks.
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            return change_stock(db, actor, data)
    except SQLAlchemyError:
        logger.exception("Stock change transaction failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.post("/import", status_code=201)
def import_inventory(data: StockImportInput, actor: StockWriter) -> StockChangeResult:
    result = record_stock_change(actor, data)
    process_committed_stock_import(data.branchId, [item.variantId for item in data.items])
    return result


@router.post("/import-csv", responses={201: {"model": CsvStockImportResult}})
def import_inventory_csv(
    actor: StockWriter, response: Response, file: Annotated[UploadFile, File()],
    branch_id: Annotated[InventoryId, Query(alias="branchId")],
    dry_run: bool = Query(default=True, alias="dryRun"),
    allow_duplicate: bool = Query(default=False, alias="allowDuplicate"),
) -> CsvStockImportResult:
    """Accepts CSV (UTF-8, ',' ';' or tab separated) and Excel .xlsx files."""
    try:
        content = file.file.read(MAX_FILE_BYTES + 1)
    finally:
        file.file.close()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, {"code": "CSV_FILE_TOO_LARGE", "maxBytes": MAX_FILE_BYTES})
    try:
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            result = import_stock_csv(
                db, actor, branch_id, content, dry_run, filename=file.filename, allow_duplicate=allow_duplicate,
            )
    except SQLAlchemyError:
        logger.exception("Stock CSV transaction failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None
    if not dry_run:
        response.status_code = 201
        process_committed_stock_import(branch_id, [item.variantId for item in result.items])
    return result


@router.post("/export", status_code=201)
def export_inventory(data: StockExportInput, actor: StockWriter) -> StockChangeResult:
    return record_stock_change(actor, data)


@router.post("/stocktake", status_code=201)
def stocktake_inventory(data: StocktakeInput, actor: StockWriter) -> StockChangeResult:
    return record_stock_change(actor, data)


@router.get("")
def get_inventory(
    actor: Reader,
    session: Database,
    branch_id: InventoryId | None = Query(default=None, alias="branchId"),
    keyword: str | None = Query(default=None, max_length=200),
    low_stock: bool = Query(default=False, alias="lowStock"),
    page: int = Query(default=1, ge=1, le=21474836),
    size: int = Query(default=50, ge=1, le=100),
) -> list[InventoryItem]:
    try:
        db = session.connection()
        if branch_id is None:
            branches = get_accessible_branch_ids(db, actor)
        else:
            require_branch_access(db, actor, branch_id)
            branches = [branch_id]
        return list_inventory(
            db, actor.store_id, branches, keyword=keyword, low_stock=low_stock,
            limit=size, offset=(page - 1) * size,
        )
    except SQLAlchemyError:
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.get("/movements")
def get_inventory_movements(
    actor: Reader, session: Database, filters: Annotated[MovementFilters, Query()],
) -> list[InventoryMovement]:
    try:
        db = session.connection()
        if filters.branchId is None:
            branches = get_accessible_branch_ids(db, actor)
        else:
            require_branch_access(db, actor, filters.branchId)
            branches = [filters.branchId]
        return list_inventory_movements(db, actor.store_id, branches, filters)
    except SQLAlchemyError:
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.get("/{branch_id}/{variant_id}")
def get_inventory_item(
    branch_id: InventoryId, variant_id: InventoryId, actor: Reader, session: Database
) -> InventoryItem:
    try:
        db = session.connection()
        require_branch_access(db, actor, branch_id)
        rows = list_inventory(db, actor.store_id, [branch_id], variant_id=variant_id, limit=1)
    except SQLAlchemyError:
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None
    if not rows:
        raise HTTPException(404, "Inventory item not found")
    return rows[0]

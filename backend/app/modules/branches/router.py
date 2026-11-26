from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import (
    Actor,
    get_accessible_branch_ids,
    require_auth,
    require_branch_access,
    require_owner,
)
from app.db.session import engine, get_db
from app.modules.branches.defaults import create_zero_inventory_rows
from app.modules.branches.schemas import (
    BranchCreatedOut,
    BranchIn,
    BranchOut,
    BranchStatus,
    BranchStatusIn,
)

router = APIRouter(prefix="/branches", tags=["branches"])
Reader = Annotated[Actor, Depends(require_auth)]
Owner = Annotated[Actor, Depends(require_owner)]
Database = Annotated[Session, Depends(get_db)]


def _out(row) -> BranchOut:
    return BranchOut(
        id=row["branch_id"],
        store_id=row["store_id"],
        branch_code=row["branch_code"],
        name=row["name"],
        address=row["address"],
        phone=row["phone"],
        status=row["status"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[BranchOut], response_model_by_alias=True)
def list_branches(
    actor: Reader,
    db: Database,
    status: BranchStatus | None = Query(default=None),
) -> list[BranchOut]:
    connection = db.connection()
    branch_ids = get_accessible_branch_ids(connection, actor)
    if not branch_ids:
        return []
    rows = connection.execute(
        text("""
            SELECT branch_id, store_id, branch_code, name, address, phone, status, created_at
            FROM branches
            WHERE store_id = :store_id AND branch_id IN :branch_ids
              AND (:status IS NULL OR status = :status)
            ORDER BY branch_code
        """).bindparams(bindparam("branch_ids", expanding=True)),
        {"store_id": actor.store_id, "branch_ids": branch_ids, "status": status},
    ).mappings()
    return [_out(row) for row in rows]


@router.get("/{branch_id}", response_model=BranchOut, response_model_by_alias=True)
def get_branch(branch_id: int, actor: Reader, db: Database) -> BranchOut:
    connection = db.connection()
    require_branch_access(connection, actor, branch_id)
    row = connection.execute(
        text("""
            SELECT branch_id, store_id, branch_code, name, address, phone, status, created_at
            FROM branches WHERE store_id = :store_id AND branch_id = :branch_id
        """),
        {"store_id": actor.store_id, "branch_id": branch_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Không tìm thấy chi nhánh")
    return _out(row)


@router.post("", status_code=201, response_model=BranchCreatedOut, response_model_by_alias=True)
def create_branch(body: BranchIn, actor: Owner) -> BranchCreatedOut:
    try:
        with engine.begin() as db:
            if db.execute(
                text("SELECT 1 FROM branches WHERE store_id = :store_id AND branch_code = :code"),
                {"store_id": actor.store_id, "code": body.branch_code},
            ).first():
                raise HTTPException(409, "Mã chi nhánh đã tồn tại trong cửa hàng")
            result = db.execute(
                text("""
                    INSERT INTO branches (store_id, branch_code, name, address, phone, status)
                    VALUES (:store_id, :code, :name, :address, :phone, 'ACTIVE')
                """),
                {
                    "store_id": actor.store_id,
                    "code": body.branch_code,
                    "name": body.name,
                    "address": body.address,
                    "phone": body.phone,
                },
            )
            branch_id = result.lastrowid
            inventory_rows = create_zero_inventory_rows(db, branch_id, actor.store_id)
            row = db.execute(
                text("""
                    SELECT branch_id, store_id, branch_code, name, address, phone, status, created_at
                    FROM branches WHERE branch_id = :branch_id
                """),
                {"branch_id": branch_id},
            ).mappings().one()
    except IntegrityError:
        raise HTTPException(409, "Mã chi nhánh đã tồn tại trong cửa hàng") from None
    return BranchCreatedOut(**_out(row).model_dump(), inventory_rows_created=inventory_rows)


@router.put("/{branch_id}", response_model=BranchOut, response_model_by_alias=True)
def update_branch(branch_id: int, body: BranchIn, actor: Owner) -> BranchOut:
    try:
        with engine.begin() as db:
            row = db.execute(
                text("SELECT 1 FROM branches WHERE store_id = :store_id AND branch_id = :branch_id"),
                {"store_id": actor.store_id, "branch_id": branch_id},
            ).first()
            if row is None:
                raise HTTPException(404, "Không tìm thấy chi nhánh")
            duplicate = db.execute(
                text("""
                    SELECT 1 FROM branches
                    WHERE store_id = :store_id AND branch_code = :code AND branch_id <> :branch_id
                """),
                {"store_id": actor.store_id, "code": body.branch_code, "branch_id": branch_id},
            ).first()
            if duplicate:
                raise HTTPException(409, "Mã chi nhánh đã tồn tại trong cửa hàng")
            db.execute(
                text("""
                    UPDATE branches SET branch_code = :code, name = :name, address = :address, phone = :phone
                    WHERE store_id = :store_id AND branch_id = :branch_id
                """),
                {
                    "store_id": actor.store_id,
                    "branch_id": branch_id,
                    "code": body.branch_code,
                    "name": body.name,
                    "address": body.address,
                    "phone": body.phone,
                },
            )
            result = db.execute(
                text("""
                    SELECT branch_id, store_id, branch_code, name, address, phone, status, created_at
                    FROM branches WHERE branch_id = :branch_id
                """),
                {"branch_id": branch_id},
            ).mappings().one()
    except IntegrityError:
        raise HTTPException(409, "Mã chi nhánh đã tồn tại trong cửa hàng") from None
    return _out(result)


@router.patch("/{branch_id}/status", response_model=BranchOut, response_model_by_alias=True)
def change_branch_status(branch_id: int, body: BranchStatusIn, actor: Owner) -> BranchOut:
    with engine.begin() as db:
        row = db.execute(
            text("SELECT 1 FROM branches WHERE store_id = :store_id AND branch_id = :branch_id"),
            {"store_id": actor.store_id, "branch_id": branch_id},
        ).first()
        if row is None:
            raise HTTPException(404, "Không tìm thấy chi nhánh")
        if body.status == "INACTIVE":
            open_orders = db.execute(
                text("""
                    SELECT COUNT(*) FROM preorders
                    WHERE branch_id = :branch_id AND status IN ('WAITING_STOCK', 'READY', 'NOTIFIED')
                """),
                {"branch_id": branch_id},
            ).scalar_one()
            if open_orders:
                raise HTTPException(409, "Không thể ngừng hoạt động khi chi nhánh còn đơn đặt trước đang xử lý")
        db.execute(
            text("UPDATE branches SET status = :status WHERE store_id = :store_id AND branch_id = :branch_id"),
            {"status": body.status, "store_id": actor.store_id, "branch_id": branch_id},
        )
        result = db.execute(
            text("""
                SELECT branch_id, store_id, branch_code, name, address, phone, status, created_at
                FROM branches WHERE branch_id = :branch_id
            """),
            {"branch_id": branch_id},
        ).mappings().one()
    return _out(result)

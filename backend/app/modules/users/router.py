from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.modules.auth.models import AuthSession, User
from app.modules.auth.schemas import UserCreate, UserInfo
from app.modules.auth.service import create_user, user_info


router = APIRouter(prefix="/users", tags=["users"])


class EmployeeUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150, strip_whitespace=True)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)


class EmployeeStatusUpdate(BaseModel):
    status: Literal["ACTIVE", "LOCKED"]


class EmployeeBranchesUpdate(BaseModel):
    branch_ids: list[int] = Field(default_factory=list, max_length=50)


class EmployeePasswordReset(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


def _employee_out(user: User, branches: list[dict] | None = None) -> dict:
    return {
        "id": user.id,
        "store_id": user.shop_id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.lower(),
        "status": user.status,
        "created_at": user.created_at,
        "branches": branches or [],
    }


def _owned_employee(db: Session, owner: User, employee_id: int) -> User:
    employee = db.scalar(
        select(User).where(User.id == employee_id, User.shop_id == owner.shop_id)
    )
    if employee is None or employee.role == "OWNER":
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản nhân viên.")
    return employee


@router.get("")
def list_store_users(
    q: str = Query(default="", max_length=200),
    role: Literal["manager", "staff"] | None = None,
    account_status: Literal["ACTIVE", "LOCKED"] | None = Query(default=None, alias="status"),
    branch_id: int | None = Query(default=None, alias="branchId", gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    owner: User = Depends(require_roles("owner", "manager")),
    db: Session = Depends(get_db),
):
    # Owners see every account in the store. Managers get a read-only view of the
    # employees assigned to their own branches (they never see other managers).
    stmt = select(User).where(User.shop_id == owner.shop_id, User.role != "OWNER")
    manager_branch_ids: list[int] | None = None
    if owner.role == "MANAGER":
        manager_branch_ids = list(db.execute(
            text("""
                SELECT ub.branch_id FROM user_branches ub
                JOIN branches b ON b.branch_id = ub.branch_id AND b.store_id = :store
                WHERE ub.user_id = :user
            """),
            {"store": owner.shop_id, "user": owner.id},
        ).scalars())
        if branch_id is not None and branch_id not in manager_branch_ids:
            raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập chi nhánh này.")
        # Managers only supervise employees; asking for managers yields nothing.
        stmt = stmt.where(User.role == "EMPLOYEE")
        visible_ids = db.execute(
            text("SELECT DISTINCT user_id FROM user_branches WHERE branch_id IN :branch_ids")
            .bindparams(bindparam("branch_ids", expanding=True)),
            {"branch_ids": manager_branch_ids or [-1]},
        ).scalars().all()
        stmt = stmt.where(User.id.in_(visible_ids))
    if role:
        stmt = stmt.where(User.role == {"manager": "MANAGER", "staff": "EMPLOYEE"}[role])
    if account_status:
        stmt = stmt.where(User.status == account_status)
    if q.strip():
        pattern = f"%{q.strip().casefold()}%"
        stmt = stmt.where(
            func.lower(User.full_name).like(pattern)
            | func.lower(User.username).like(pattern)
            | func.lower(User.email).like(pattern)
            | func.lower(User.phone).like(pattern)
        )
    if branch_id is not None:
        branch = db.execute(
            text("SELECT branch_id FROM branches WHERE branch_id=:branch AND store_id=:store"),
            {"branch": branch_id, "store": owner.shop_id},
        ).scalar_one_or_none()
        if branch is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh.")
        assigned_user_ids = db.execute(
            text("SELECT user_id FROM user_branches WHERE branch_id=:branch"),
            {"branch": branch_id},
        ).scalars().all()
        stmt = stmt.where(User.id.in_(assigned_user_ids))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(
        stmt.order_by(User.role, User.full_name, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    user_ids = [user.id for user in users]
    branch_map: dict[int, list[dict]] = {user_id: [] for user_id in user_ids}
    if user_ids:
        assignments = db.execute(
            text("""
                SELECT ub.user_id AS user_id, b.branch_id AS id, b.branch_code AS branch_code,
                       b.name AS name, b.status AS status
                FROM user_branches ub JOIN branches b ON b.branch_id=ub.branch_id
                WHERE ub.user_id IN :user_ids AND b.store_id=:store
                ORDER BY b.name
            """).bindparams(bindparam("user_ids", expanding=True)),
            {"user_ids": user_ids, "store": owner.shop_id},
        ).mappings()
        for branch in assignments:
            if manager_branch_ids is not None and branch["id"] not in manager_branch_ids:
                continue
            branch_map[branch["user_id"]].append(
                {"id": branch["id"], "branch_code": branch["branch_code"],
                 "name": branch["name"], "status": branch["status"]}
            )
    return {
        "items": [_employee_out(user, branch_map[user.id]) for user in users],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
def add_store_user(
    payload: UserCreate,
    owner: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    duplicate = db.scalar(select(User.id).where(func.lower(User.username) == payload.username.casefold()))
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập này đã được sử dụng.")

    if payload.email is not None:
        duplicate_email = db.scalar(
            select(User.id).where(func.lower(User.email) == payload.email.casefold())
        )
        if duplicate_email is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được dùng cho tài khoản khác.")

    branch_ids = payload.branch_ids
    if branch_ids:
        active_branch_ids = set(db.execute(
            text("""
                SELECT branch_id FROM branches
                WHERE store_id=:store AND status='ACTIVE' AND branch_id IN :branch_ids
            """).bindparams(bindparam("branch_ids", expanding=True)),
            {"store": owner.shop_id, "branch_ids": branch_ids},
        ).scalars())
        invalid = sorted(set(branch_ids) - active_branch_ids)
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_BRANCH_ASSIGNMENT", "branchIds": invalid},
            )

    user = create_user(
        db,
        shop=owner.shop,
        username=payload.username,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        email=payload.email,
    )
    user.phone = payload.phone
    try:
        db.flush()
        for branch_id in branch_ids:
            db.execute(
                text("INSERT INTO user_branches (user_id, branch_id) VALUES (:user, :branch)"),
                {"user": user.id, "branch": branch_id},
            )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập này đã được sử dụng.")
    return user_info(user)


@router.put("/{employee_id}")
def update_store_user(
    employee_id: int,
    payload: EmployeeUpdate,
    owner: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    employee = _owned_employee(db, owner, employee_id)
    email = payload.email.strip().casefold() if payload.email else None
    if email and db.scalar(
        select(User.id).where(func.lower(User.email) == email, User.id != employee_id)
    ):
        raise HTTPException(status_code=409, detail="Email đã được dùng cho tài khoản khác.")
    employee.full_name = payload.full_name
    employee.email = email
    employee.phone = payload.phone.strip() if payload.phone else None
    db.commit()
    db.refresh(employee)
    return _employee_out(employee)


@router.patch("/{employee_id}/status")
def update_store_user_status(
    employee_id: int,
    payload: EmployeeStatusUpdate,
    owner: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    employee = _owned_employee(db, owner, employee_id)
    employee.status = payload.status
    if payload.status == "LOCKED":
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == employee_id, AuthSession.revoked.is_(False))
            .values(revoked=True)
        )
    db.commit()
    db.refresh(employee)
    return _employee_out(employee)


@router.put("/{employee_id}/branches")
def replace_store_user_branches(
    employee_id: int,
    payload: EmployeeBranchesUpdate,
    owner: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    employee = _owned_employee(db, owner, employee_id)
    branch_ids = sorted(set(payload.branch_ids))
    if any(branch_id <= 0 for branch_id in branch_ids):
        raise HTTPException(status_code=422, detail="Branch ids must be positive.")
    if branch_ids:
        active_branch_ids = set(db.execute(
            text("""
                SELECT branch_id FROM branches
                WHERE store_id=:store AND status='ACTIVE' AND branch_id IN :branch_ids
            """).bindparams(bindparam("branch_ids", expanding=True)),
            {"store": owner.shop_id, "branch_ids": branch_ids},
        ).scalars())
        invalid = sorted(set(branch_ids) - active_branch_ids)
        if invalid:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_BRANCH_ASSIGNMENT", "branchIds": invalid},
            )

    db.execute(text("DELETE FROM user_branches WHERE user_id=:user"), {"user": employee.id})
    for branch_id in branch_ids:
        db.execute(
            text("INSERT INTO user_branches (user_id, branch_id) VALUES (:user, :branch)"),
            {"user": employee.id, "branch": branch_id},
        )
    db.commit()
    branches = db.execute(
        text("""
            SELECT branch_id AS id, branch_code, name, status FROM branches
            WHERE store_id=:store AND branch_id IN :branch_ids ORDER BY name
        """).bindparams(bindparam("branch_ids", expanding=True)),
        {"store": owner.shop_id, "branch_ids": branch_ids},
    ).mappings().all() if branch_ids else []
    return _employee_out(employee, [dict(branch) for branch in branches])


@router.post("/{employee_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_store_user_password(
    employee_id: int,
    payload: EmployeePasswordReset,
    owner: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    employee = _owned_employee(db, owner, employee_id)
    employee.password_hash = hash_password(payload.new_password)
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == employee_id, AuthSession.revoked.is_(False))
        .values(revoked=True)
    )
    db.commit()

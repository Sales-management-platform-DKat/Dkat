from datetime import timezone
from dataclasses import dataclass

Every data route must go through at least `require_auth`. Rules:

    require_auth            Bearer token -> verify JWT -> reload user from DB -> request.state.user
                            401 UNAUTHORIZED / TOKEN_EXPIRED / INVALID_TOKEN, 403 ACCOUNT_LOCKED
    require_role(*roles)    403 FORBIDDEN when user.role is not in `roles`
    require_branch_access() branch_id from path / query / JSON body:
                              OWNER            -> any branch of their own store
                              MANAGER/EMPLOYEE -> only branches assigned in user_branches
                            otherwise 403 FORBIDDEN
    get_accessible_branch_ids(user)
                            list of branch ids the user may see -> use it to filter list queries:
                            `WHERE branch_id IN (:ids)`

Usage in a router:

    @router.post("", status_code=201)
    async def create(body: In, user: CurrentUser = Depends(require_role(ROLE_OWNER))): ...

    @router.get("/branches/{branch_id}/inventory")
    async def list_inventory(branch_id: int, user: CurrentUser = Depends(require_branch_access())): ...

    @router.get("/sales")
    async def list_sales(user: CurrentUser = Depends(require_auth), db = Depends(get_db)):
        ids = get_accessible_branch_ids(user)   # then filter by these ids in the repository

require_auth reloads the user from DB on every request, so a LOCKED or deleted account (or a removed
branch assignment) takes effect immediately even if the token has not expired yet.
FastAPI caches `require_auth` per request, so combining require_role + require_branch_access costs one lookup.
"""
from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.auth import repository as auth_repo

ROLE_OWNER = "OWNER"
ROLE_MANAGER = "MANAGER"
ROLE_EMPLOYEE = "EMPLOYEE"
ALL_ROLES = (ROLE_OWNER, ROLE_MANAGER, ROLE_EMPLOYEE)

# Names accepted for the branch id (snake_case for path/query, camelCase for JSON bodies)
BRANCH_ID_KEYS = ("branch_id", "branchId")

FORBIDDEN_ROLE_MESSAGE = "Bạn không có quyền thực hiện thao tác này"
FORBIDDEN_BRANCH_MESSAGE = "Bạn không được phân công tại chi nhánh này"

_bearer = HTTPBearer(auto_error=False)  # auto_error=False -> we return our own 401 format


@dataclass
class CurrentUser:
    id: int | None = None
    role: str | None = None
    store_id: int | None = None
    # OWNER: every branch of the store (any status). MANAGER/EMPLOYEE: assigned ACTIVE branches.
    branch_ids: list[int] = field(default_factory=list)

    @property
    def is_owner(self) -> bool:
        return self.role == ROLE_OWNER


# --------------------------------------------------------------------------- authentication


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError.unauthorized("Thiếu token đăng nhập")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Phiên đăng nhập đã hết hạn")
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise AppError(401, "INVALID_TOKEN", "Token không hợp lệ")

    user = await auth_repo.get_user_by_id(db, user_id)
    if user is None:
        raise AppError(401, "INVALID_TOKEN", "Token không hợp lệ")
    if user.status == "LOCKED":
        raise AppError(403, "ACCOUNT_LOCKED", "Tài khoản đã bị khóa. Vui lòng liên hệ quản lý cửa hàng")

    # Role and branches come from the DB, never from the token payload (token may be stale)
    current = CurrentUser(
        id=user.user_id,
        role=user.role,
        store_id=user.store_id,
        branch_ids=await auth_repo.list_accessible_branch_ids(db, user),
    )
    request.state.user = current
    return current


# --------------------------------------------------------------------------- roles


def require_role(*roles: str):
    """Example: Depends(require_role(ROLE_OWNER, ROLE_MANAGER)). Wrong role -> 403 FORBIDDEN."""
    unknown = set(roles) - set(ALL_ROLES)
    if not roles or unknown:  # fail at import time instead of silently denying everyone
        raise ValueError(f"require_role: invalid roles {sorted(unknown) or '(none)'}")

    async def checker(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if user.role not in roles:
            raise AppError.forbidden(FORBIDDEN_ROLE_MESSAGE)
        return user

    return dependency


@dataclass(frozen=True)
class Actor:
    store_id: int
    role: str
    user_id: int


def require_auth(user: User = Depends(get_current_user)) -> Actor:
    return Actor(store_id=user.shop_id, role=user.role, user_id=user.id)


def require_owner(user: User = Depends(require_roles("owner"))) -> Actor:
    return Actor(store_id=user.shop_id, role=user.role, user_id=user.id)


def get_accessible_branch_ids(db: Connection, actor: Actor, branch_id: int | None = None) -> list[int]:
    return list(db.execute(
        text("""
            SELECT b.branch_id
            FROM branches AS b
            WHERE b.store_id = :store_id
              AND (:branch_id IS NULL OR b.branch_id = :branch_id)
              AND (:owner OR EXISTS (
                  SELECT 1 FROM user_branches AS ub
                  WHERE ub.branch_id = b.branch_id AND ub.user_id = :user_id
              ))
        """),
        {
            "store_id": actor.store_id,
            "branch_id": branch_id,
            "owner": actor.role == "OWNER",
            "user_id": actor.user_id,
        },
    ).scalars())


def require_branch_access(db: Connection, actor: Actor, branch_id: int) -> None:
    if not get_accessible_branch_ids(db, actor, branch_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền truy cập chi nhánh này.")

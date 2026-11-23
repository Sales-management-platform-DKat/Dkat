"""Authentication / authorization dependencies (FR-01.4, NFR-02, BR-10).

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
from sqlalchemy.ext.asyncio import AsyncSession

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

    checker.dkat_roles = roles  # read by scripts/gen_api_docs.py to document who may call a route
    return checker


# --------------------------------------------------------------------------- branch scope


def get_accessible_branch_ids(user: CurrentUser) -> list[int]:
    """Branch ids `user` may read/write. Use it to filter list queries by permission.

    OWNER -> every branch of their store; MANAGER/EMPLOYEE -> branches assigned in user_branches.
    An empty list means "no branch" (return an empty result, never "no filter").
    """
    return list(user.branch_ids)


def can_access_branch(user: CurrentUser, branch_id: int) -> bool:
    return branch_id in user.branch_ids


async def ensure_branch_access(db: AsyncSession, user: CurrentUser, branch_id: int) -> None:
    """Raise unless `user` may work on `branch_id`. Call it from a service when the branch id
    is not in the request itself (e.g. it comes from a loaded order or transfer)."""
    if can_access_branch(user, branch_id):
        return
    if user.is_owner and not await auth_repo.branch_exists(db, branch_id):
        # OWNER may know every branch of the store; tell them the id is wrong.
        # MANAGER/EMPLOYEE always get 403 so they cannot probe which ids exist.
        raise AppError.not_found("Không tìm thấy chi nhánh")
    raise AppError.forbidden(FORBIDDEN_BRANCH_MESSAGE)


async def _read_json_body(request: Request) -> Any:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    if "application/json" not in request.headers.get("content-type", ""):
        return None
    try:
        return await request.json()  # Starlette caches the body, the route can still read it
    except Exception:  # invalid JSON is reported by FastAPI's own validation
        return None


async def _find_branch_id(request: Request, param: str) -> int | None:
    """Collect branch_id from path, query and JSON body. All values present must agree."""
    keys = (param, *(k for k in BRANCH_ID_KEYS if k != param))
    found: list[Any] = []
    for source in (request.path_params, request.query_params):
        found += [source[k] for k in keys if source.get(k) not in (None, "")]
    body = await _read_json_body(request)
    if isinstance(body, dict):
        found += [body[k] for k in keys if body.get(k) not in (None, "")]
    if not found:
        return None

    ids: set[int] = set()
    for raw in found:
        if isinstance(raw, bool):
            raise AppError.bad_request(f"{param} không hợp lệ")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise AppError.bad_request(f"{param} không hợp lệ")
        if value <= 0 or str(raw).strip() != str(value):
            raise AppError.bad_request(f"{param} không hợp lệ")
        ids.add(value)
    if len(ids) > 1:
        # e.g. path says branch 1 but body says branch 2: refuse instead of guessing which one is used
        raise AppError.bad_request(f"{param} trong đường dẫn, query và body không khớp nhau")
    return ids.pop()


def require_branch_access(param: str = "branch_id", *, required: bool = False):
    """Check the branch named in the request.

    Looks for `param` (and branch_id / branchId) in path params, query string and JSON body.
    - not present: pass through (required=False) or 400 (required=True)
    - present: OWNER passes for every branch of their store; MANAGER/EMPLOYEE only for assigned
      branches; otherwise 403 FORBIDDEN.
    The checked id is stored in request.state.branch_id.
    """

    async def checker(
        request: Request,
        user: CurrentUser = Depends(require_auth),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        branch_id = await _find_branch_id(request, param)
        if branch_id is None:
            if required:
                raise AppError.bad_request(f"Thiếu {param}")
            return user
        await ensure_branch_access(db, user, branch_id)
        request.state.branch_id = branch_id
        return user

    checker.dkat_branch_scope = True  # read by scripts/gen_api_docs.py
    return checker

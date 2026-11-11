"""Authentication / authorization dependencies.

Usage in a router:
    @router.post("", dependencies=[Depends(require_role("OWNER", "MANAGER"))])

    @router.get("/branches/{branch_id}/inventory")
    async def list_inventory(branch_id: int, user=Depends(require_branch_access())): ...

require_auth reads `Authorization: Bearer <token>`, verifies the JWT, then reloads the user from DB
so a LOCKED or deleted account is rejected immediately even if its token has not expired.
"""
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.auth import repository as auth_repo

_bearer = HTTPBearer(auto_error=False)  # auto_error=False -> we return our own 401 format


@dataclass
class CurrentUser:
    id: int | None = None
    role: str | None = None
    store_id: int | None = None
    branch_ids: list[int] = field(default_factory=list)


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

    branches = await auth_repo.list_user_branches(db, user)
    current = CurrentUser(
        id=user.user_id,
        role=user.role,
        store_id=user.store_id,
        branch_ids=[b.branch_id for b in branches],
    )
    request.state.user = current
    return current


def require_role(*roles: str):
    """Example: Depends(require_role("OWNER", "MANAGER"))."""

    async def checker(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if user.role not in roles:
            raise AppError.forbidden("Bạn không có quyền thực hiện thao tác này")
        return user

    return checker


def require_branch_access(param: str = "branch_id"):
    """Reads branch_id from path or query (name set by `param`); 403 if the user is not assigned to it."""

    async def checker(request: Request, user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        raw = request.path_params.get(param) or request.query_params.get(param)
        if raw is None:
            return user
        try:
            branch_id = int(raw)
        except ValueError:
            raise AppError.bad_request(f"Invalid {param}")
        if branch_id not in user.branch_ids:
            raise AppError.forbidden("Bạn không được phân công tại chi nhánh này")
        return user

    return checker

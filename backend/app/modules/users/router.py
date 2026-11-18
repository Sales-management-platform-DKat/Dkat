"""Internal account management API (FR-01.3). OWNER and MANAGER only; EMPLOYEE -> 403.

GET    /users                         list accounts in the caller's scope
GET    /users/{id}
POST   /users                         201; MANAGER may only create EMPLOYEE in their own branches
PUT    /users/{id}                    fullName, email, phone (+ role: OWNER only)
PATCH  /users/{id}/status             ACTIVE / LOCKED
POST   /users/{id}/reset-password     new password typed by the manager
Responses never contain password_hash (UserOut has no such field).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_MANAGER, ROLE_OWNER, CurrentUser, require_role
from app.db.session import get_db
from app.modules.users import service
from app.modules.users.schemas import ResetPasswordIn, UserCreateIn, UserOut, UserStatusIn, UserUpdateIn
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/users", tags=["users"])

# Checked before body validation, so an EMPLOYEE gets 403 instead of 422
_managers = require_role(ROLE_OWNER, ROLE_MANAGER)


@router.get("", response_model=SuccessResponse[list[UserOut]], response_model_by_alias=True)
async def list_users(user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)):
    """OWNER: mọi tài khoản của cửa hàng. MANAGER: nhân viên thuộc chi nhánh mình quản lý."""
    return ok(await service.list_users(db, user))


@router.get("/{user_id}", response_model=SuccessResponse[UserOut], response_model_by_alias=True)
async def get_user(user_id: int, user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)):
    return ok(await service.get_user(db, user, user_id))


@router.post("", status_code=201, response_model=SuccessResponse[UserOut], response_model_by_alias=True)
async def create_user(body: UserCreateIn, user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)):
    """Tạo MANAGER/EMPLOYEE. 409 DUPLICATE_USERNAME, 422 mật khẩu < 8 ký tự hoặc chi nhánh không hợp lệ."""
    return ok(await service.create_user(db, user, body))


@router.put("/{user_id}", response_model=SuccessResponse[UserOut], response_model_by_alias=True)
async def update_user(
    user_id: int, body: UserUpdateIn, user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)
):
    """Sửa họ tên, email, SĐT. `role` chỉ OWNER được đổi (MANAGER -> 403)."""
    return ok(await service.update_user(db, user, user_id, body))


@router.patch("/{user_id}/status", response_model=SuccessResponse[UserOut], response_model_by_alias=True)
async def change_user_status(
    user_id: int, body: UserStatusIn, user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)
):
    """ACTIVE/LOCKED. 409 CANNOT_LOCK_SELF, 409 LAST_ACTIVE_OWNER."""
    return ok(await service.change_status(db, user, user_id, body.status))


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int, body: ResetPasswordIn, user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)
):
    """Đặt mật khẩu mới (>= 8 ký tự). Không dùng cho chính mình: 409 CANNOT_RESET_OWN_PASSWORD."""
    await service.reset_password(db, user, user_id, body)
    return ok(None)

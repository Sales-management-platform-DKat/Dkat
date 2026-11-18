"""Internal account management API (FR-01.3). OWNER and MANAGER only; EMPLOYEE -> 403.

GET    /users?branchId&role&status&keyword&page&pageSize   paged list in the caller's scope
GET    /users/{id}                    includes the assigned branches
POST   /users                         201; MANAGER may only create EMPLOYEE in their own branches
PUT    /users/{id}                    fullName, email, phone (+ role: OWNER only)
PUT    /users/{id}/branches           replace the branch assignment (FR-02.4)
PATCH  /users/{id}/status             ACTIVE / LOCKED
POST   /users/{id}/reset-password     new password typed by the manager
Responses never contain password_hash (UserOut has no such field).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_MANAGER, ROLE_OWNER, CurrentUser, require_branch_access, require_role
from app.db.session import get_db
from app.modules.users import service
from app.modules.users.schemas import (
    MAX_PAGE_SIZE,
    AnyRole,
    ResetPasswordIn,
    UserBranchesIn,
    UserCreateIn,
    UserOut,
    UserPageOut,
    UserStatus,
    UserStatusIn,
    UserUpdateIn,
)
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/users", tags=["users"])

# Checked before body validation, so an EMPLOYEE gets 403 instead of 422
_managers = require_role(ROLE_OWNER, ROLE_MANAGER)


@router.get(
    "",
    dependencies=[Depends(_managers)],
    response_model=SuccessResponse[UserPageOut],
    response_model_by_alias=True,
)
async def list_users(
    branch_id: int | None = Query(default=None, alias="branchId", gt=0),
    role: AnyRole | None = Query(default=None),
    status: UserStatus | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=MAX_PAGE_SIZE),
    # role is checked first (route dependencies), then branchId must be one of the caller's branches
    user: CurrentUser = Depends(require_branch_access()),
    db: AsyncSession = Depends(get_db),
):
    """OWNER: mọi tài khoản. MANAGER: nhân viên thuộc chi nhánh mình; branchId ngoài phạm vi -> 403.
    keyword tìm trong username, họ tên, email, SĐT."""
    return ok(
        await service.list_users(
            db, user, branch_id=branch_id, role=role, status=status, keyword=keyword, page=page, page_size=page_size
        )
    )


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


@router.put("/{user_id}/branches", response_model=SuccessResponse[UserOut], response_model_by_alias=True)
async def assign_branches(
    user_id: int, body: UserBranchesIn, user: CurrentUser = Depends(_managers), db: AsyncSession = Depends(get_db)
):
    """Thay toàn bộ phân công chi nhánh. MANAGER chỉ dùng chi nhánh mình quản lý (khác -> 403).
    Có hiệu lực ngay ở request kế tiếp và khi đăng nhập lại."""
    return ok(await service.assign_branches(db, user, user_id, body))


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

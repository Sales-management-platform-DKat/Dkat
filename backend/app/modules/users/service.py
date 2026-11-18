"""Internal account management (FR-01.3).

Who can manage whom:
- OWNER: every account of their store.
- MANAGER: only EMPLOYEE accounts whose ACTIVE branches all lie inside the manager's own branches
  (an employee who also works at another manager's branch is OWNER-only). Outside that scope -> 403,
  also for ids that do not exist, so a manager cannot probe which accounts exist.
- EMPLOYEE: nothing (blocked in the router).

Rules: accounts are created as MANAGER/EMPLOYEE only; usernames are unique (409 DUPLICATE_USERNAME);
passwords are bcrypt-hashed and never returned; a user cannot lock themself or reset their own password
here (use /auth/change-password); the last ACTIVE owner of a store cannot be locked.
Locking takes effect on the next request: require_auth reloads the account and rejects LOCKED.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import ROLE_EMPLOYEE, ROLE_OWNER, CurrentUser, get_accessible_branch_ids
from app.core.security import hash_password
from app.db.session import transaction
from app.modules.branches.models import Branch
from app.modules.users import repository
from app.modules.users.models import User
from app.modules.users.schemas import (
    AssignedBranchOut,
    ResetPasswordIn,
    UserBranchesIn,
    UserCreateIn,
    UserOut,
    UserPageOut,
    UserUpdateIn,
)
from app.utils.logger import get_logger

logger = get_logger("app.users")

OUT_OF_SCOPE_MESSAGE = "Bạn không có quyền quản lý tài khoản này"


def _to_out(user: User, branches: list[Branch]) -> UserOut:
    return UserOut(
        id=user.user_id,
        store_id=user.store_id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        branches=[
            AssignedBranchOut(id=b.branch_id, branch_code=b.branch_code, name=b.name, status=b.status) for b in branches
        ],
    )


def _in_manager_scope(actor: CurrentUser, target: User, branches: list[Branch]) -> bool:
    active = {b.branch_id for b in branches if b.status == "ACTIVE"}
    return target.role == ROLE_EMPLOYEE and bool(active) and active <= set(actor.branch_ids)


async def _load_target(
    db: AsyncSession, actor: CurrentUser, user_id: int, *, for_update: bool = False
) -> tuple[User, list[Branch]]:
    user = await repository.get_user(db, actor.store_id, user_id, for_update=for_update)
    branches = (await repository.branches_by_user(db, [user.user_id])).get(user.user_id, []) if user else []
    if actor.is_owner:
        if user is None:
            raise AppError.not_found("Không tìm thấy tài khoản")
    elif user is None or not _in_manager_scope(actor, user, branches):
        raise AppError.forbidden(OUT_OF_SCOPE_MESSAGE)
    return user, branches


def _duplicate_username(username: str) -> AppError:
    return AppError(
        409,
        "DUPLICATE_USERNAME",
        f"Tên đăng nhập '{username}' đã được sử dụng",
        [{"field": "username", "message": "Username already exists", "type": "duplicate"}],
    )


# --------------------------------------------------------------------------- read


async def list_users(
    db: AsyncSession,
    actor: CurrentUser,
    *,
    branch_id: int | None,
    role: str | None,
    status: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> UserPageOut:
    """branch_id has already been checked by require_branch_access (MANAGER: must be one of theirs)."""
    users, total = await repository.list_users_page(
        db,
        actor.store_id,
        manager_branch_ids=None if actor.is_owner else get_accessible_branch_ids(actor),
        branch_id=branch_id,
        role=role,
        status=status,
        keyword=keyword.strip() if keyword else None,
        page=page,
        page_size=page_size,
    )
    branches = await repository.branches_by_user(db, [u.user_id for u in users])
    return UserPageOut(
        items=[_to_out(u, branches.get(u.user_id, [])) for u in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )


async def get_user(db: AsyncSession, actor: CurrentUser, user_id: int) -> UserOut:
    return _to_out(*await _load_target(db, actor, user_id))


# --------------------------------------------------------------------------- write


async def create_user(db: AsyncSession, actor: CurrentUser, body: UserCreateIn) -> UserOut:
    if not actor.is_owner:
        if body.role != ROLE_EMPLOYEE:
            raise AppError.forbidden("Quản lý chỉ được tạo tài khoản nhân viên (EMPLOYEE)")
        outside = sorted(set(body.branch_ids) - set(actor.branch_ids))
        if outside:
            raise AppError(403, "FORBIDDEN", "Chỉ được gán nhân viên vào chi nhánh bạn quản lý", {"branchIds": outside})

    invalid = sorted(set(body.branch_ids) - await repository.active_branch_ids(db, actor.store_id, body.branch_ids))
    if invalid:
        raise AppError.validation(
            "Chi nhánh không tồn tại hoặc đã ngừng hoạt động",
            [{"field": "branchIds", "message": f"Invalid branch ids: {invalid}", "type": "invalid_branch"}],
        )
    if await repository.username_exists(db, body.username):
        raise _duplicate_username(body.username)

    password_hash = await hash_password(body.password)  # slow (bcrypt): outside the transaction
    try:
        async with transaction(db):
            user = await repository.insert_user(
                db,
                User(
                    store_id=actor.store_id,
                    username=body.username,
                    password_hash=password_hash,
                    full_name=body.full_name,
                    email=body.email,
                    phone=body.phone,
                    role=body.role,
                ),
                body.branch_ids,
            )
    except IntegrityError as exc:
        if getattr(getattr(exc, "orig", None), "args", [None])[0] == 1062:  # same username at the same time
            raise _duplicate_username(body.username) from exc
        raise
    logger.info("USER_CREATED id=%s username=%r role=%s by user_id=%s", user.user_id, user.username, user.role, actor.id)
    return await get_user(db, actor, user.user_id)


async def update_user(db: AsyncSession, actor: CurrentUser, user_id: int, body: UserUpdateIn) -> UserOut:
    user, branches = await _load_target(db, actor, user_id)
    role_changes = body.role is not None and body.role != user.role
    if role_changes:
        if not actor.is_owner:
            raise AppError.forbidden("Chỉ chủ cửa hàng (OWNER) được đổi vai trò")
        if user.role == ROLE_OWNER:
            raise AppError(409, "CANNOT_CHANGE_OWNER_ROLE", "Không thể đổi vai trò của chủ cửa hàng")

    async with transaction(db):
        user.full_name = body.full_name
        user.email = body.email
        user.phone = body.phone
        if role_changes:
            user.role = body.role
        user = await repository.save_user(db, user)
    logger.info("USER_UPDATED id=%s by user_id=%s role_changed=%s", user_id, actor.id, role_changes)
    return _to_out(user, branches)


async def change_status(db: AsyncSession, actor: CurrentUser, user_id: int, status: str) -> UserOut:
    if status == "LOCKED" and user_id == actor.id:
        raise AppError(409, "CANNOT_LOCK_SELF", "Không thể tự khóa tài khoản của chính mình")

    async with transaction(db):
        user, branches = await _load_target(db, actor, user_id, for_update=True)
        if user.status == status:
            return _to_out(user, branches)  # idempotent
        if status == "LOCKED" and user.role == ROLE_OWNER and await repository.lock_active_owners(db, actor.store_id) <= 1:
            raise AppError(409, "LAST_ACTIVE_OWNER", "Không thể khóa chủ cửa hàng duy nhất đang hoạt động")
        user.status = status
        user = await repository.save_user(db, user)
    logger.info("USER_STATUS id=%s status=%s by user_id=%s", user_id, status, actor.id)
    return _to_out(user, branches)


async def assign_branches(db: AsyncSession, actor: CurrentUser, user_id: int, body: UserBranchesIn) -> UserOut:
    """Replace the user's branch assignment (FR-02.4).

    OWNER: the new set is exactly body.branchIds.
    MANAGER: may only use their own branches; assignments outside them (e.g. an INACTIVE branch of
    another manager) are kept untouched, so a manager can never remove what they cannot see.
    Takes effect on the next request (require_auth reloads branches) and on the next login.
    """
    requested = set(body.branch_ids)
    if not actor.is_owner:
        outside = sorted(requested - set(actor.branch_ids))
        if outside:
            raise AppError(403, "FORBIDDEN", "Chỉ được phân công vào chi nhánh bạn quản lý", {"branchIds": outside})
    invalid = sorted(requested - await repository.active_branch_ids(db, actor.store_id, sorted(requested)))
    if invalid:
        raise AppError.validation(
            "Chi nhánh không tồn tại hoặc đã ngừng hoạt động",
            [{"field": "branchIds", "message": f"Invalid branch ids: {invalid}", "type": "invalid_branch"}],
        )

    async with transaction(db):
        # Row lock: two managers editing the same account are applied one after the other
        user, _ = await _load_target(db, actor, user_id, for_update=True)
        if user.role == ROLE_OWNER:
            raise AppError(409, "OWNER_HAS_ALL_BRANCHES", "Chủ cửa hàng luôn được truy cập mọi chi nhánh, không cần phân công")
        new_ids = requested
        if not actor.is_owner:
            kept = await repository.assigned_branch_ids(db, user.user_id) - set(actor.branch_ids)
            new_ids = requested | kept
        await repository.replace_user_branches(db, user.user_id, new_ids)
    logger.info("USER_BRANCHES id=%s branches=%s by user_id=%s", user_id, sorted(new_ids), actor.id)
    # Still in a MANAGER's scope afterwards: kept rows are outside their branches only if INACTIVE
    return await get_user(db, actor, user_id)


async def reset_password(db: AsyncSession, actor: CurrentUser, user_id: int, body: ResetPasswordIn) -> None:
    if user_id == actor.id:
        # Resetting without the old password would let a stolen token take over the account
        raise AppError(409, "CANNOT_RESET_OWN_PASSWORD", "Hãy dùng chức năng đổi mật khẩu (/auth/change-password)")
    user, _ = await _load_target(db, actor, user_id)
    password_hash = await hash_password(body.new_password)
    async with transaction(db):
        await repository.set_password_hash(db, user.user_id, password_hash)
    logger.info("USER_PASSWORD_RESET id=%s by user_id=%s", user_id, actor.id)  # never log the password

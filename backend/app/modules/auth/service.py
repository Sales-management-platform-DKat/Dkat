"""Login, current user, logout, change password (FR-01.1, FR-01.2, FR-01.5)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.permissions import CurrentUser
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import transaction
from app.modules.auth import repository
from app.modules.auth.schemas import AuthUserOut, BranchBrief, ChangePasswordIn, LoginIn, LoginOut
from app.modules.users.models import User
from app.utils.logger import get_logger

logger = get_logger("app.auth")

# Same message for "unknown username" and "wrong password": never reveal which one was wrong
INVALID_CREDENTIALS_MESSAGE = "Tên đăng nhập hoặc mật khẩu không đúng"


async def _build_user_out(db: AsyncSession, user: User) -> AuthUserOut:
    branches = await repository.list_user_branches(db, user)
    return AuthUserOut(
        id=user.user_id,
        full_name=user.full_name,
        username=user.username,
        role=user.role,
        store_id=user.store_id,
        branches=[BranchBrief(id=b.branch_id, name=b.name) for b in branches],
    )


async def login(db: AsyncSession, body: LoginIn, client_ip: str | None) -> LoginOut:
    user = await repository.get_user_by_username(db, body.username)

    # Always run bcrypt (dummy hash if user missing) so timing does not reveal valid usernames
    password_ok = await verify_password(body.password, user.password_hash if user else None)
    if not password_ok:
        reason = "unknown_username" if user is None else "wrong_password"
        logger.warning("LOGIN_FAILED username=%r ip=%s reason=%s", body.username, client_ip, reason)
        raise AppError(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS_MESSAGE)

    # Lock status is only revealed to someone who already knows the correct password
    if user.status == "LOCKED":
        logger.warning("LOGIN_FAILED username=%r ip=%s reason=account_locked", body.username, client_ip)
        raise AppError(403, "ACCOUNT_LOCKED", "Tài khoản đã bị khóa. Vui lòng liên hệ quản lý cửa hàng")

    user_out = await _build_user_out(db, user)
    token = create_access_token(
        user_id=user.user_id,
        role=user.role,
        store_id=user.store_id,
        branch_ids=[b.id for b in user_out.branches],
    )
    logger.info("LOGIN_OK user_id=%s username=%r ip=%s", user.user_id, user.username, client_ip)
    return LoginOut(token=token, expires_in=settings.JWT_EXPIRE_HOURS * 3600, user=user_out)


async def get_me(db: AsyncSession, current: CurrentUser) -> AuthUserOut:
    user = await repository.get_user_by_id(db, current.id)
    if user is None:  # deleted between require_auth and here
        raise AppError.unauthorized("Phiên đăng nhập không hợp lệ")
    return await _build_user_out(db, user)


def logout(current: CurrentUser, client_ip: str | None) -> None:
    # JWT is stateless: the client deletes the token. We only record the event.
    logger.info("LOGOUT user_id=%s ip=%s", current.id, client_ip)


async def change_password(db: AsyncSession, current: CurrentUser, body: ChangePasswordIn, client_ip: str | None) -> None:
    user = await repository.get_user_by_id(db, current.id)
    if user is None:
        raise AppError.unauthorized("Phiên đăng nhập không hợp lệ")

    # 400 (not 401) so the frontend does not treat it as an expired session
    if not await verify_password(body.old_password, user.password_hash):
        logger.warning("CHANGE_PASSWORD_FAILED user_id=%s ip=%s reason=wrong_old_password", user.user_id, client_ip)
        raise AppError(400, "INVALID_OLD_PASSWORD", "Mật khẩu hiện tại không đúng")
    if body.new_password == body.old_password:
        raise AppError.validation(
            "Mật khẩu mới phải khác mật khẩu hiện tại",
            [{"field": "newPassword", "message": "Must differ from oldPassword", "type": "same_as_old"}],
        )

    new_hash = await hash_password(body.new_password)
    async with transaction(db):
        await repository.update_password_hash(db, user.user_id, new_hash)
    logger.info("CHANGE_PASSWORD_OK user_id=%s ip=%s", user.user_id, client_ip)

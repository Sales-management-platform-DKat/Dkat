from datetime import timezone
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.security import hash_access_token
from app.db.session import get_db
from app.modules.auth.models import AuthSession, User
from app.modules.auth.service import subscription_is_active, utcnow


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập.")

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_access_token(credentials.credentials),
            AuthSession.revoked.is_(False),
        )
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ.")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    user = session.user
    if expires_at <= utcnow() or user.status != "ACTIVE" or not subscription_is_active(user.shop):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn.")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        role = {"OWNER": "owner", "MANAGER": "manager", "EMPLOYEE": "staff"}[user.role]
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền thực hiện thao tác này.")
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


def require_owner_or_manager(user: User = Depends(require_roles("owner", "manager"))) -> Actor:
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
            "store_id": actor.store_id, "branch_id": branch_id,
            "owner": actor.role == "OWNER", "user_id": actor.user_id,
        },
    ).scalars())


def require_branch_access(db: Connection, actor: Actor, branch_id: int) -> None:
    if not get_accessible_branch_ids(db, actor, branch_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền truy cập chi nhánh này.")

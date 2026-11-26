from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import config
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_access_token,
    refresh_token_is_persistent,
    verify_password,
)
from app.modules.auth.models import AuthSession, Shop, StoreSubscription, User


STORAGE_ROLES = {"owner": "OWNER", "manager": "MANAGER", "staff": "EMPLOYEE"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def subscription_is_active(shop: Shop, now: datetime | None = None) -> bool:
    subscription = shop.subscriptions[-1] if shop.subscriptions else None
    if subscription is None or subscription.status != "ACTIVE":
        return False
    expires_at = subscription.subscription_expires_at
    current_time = now or utcnow()
    if expires_at.tzinfo is None:
        return expires_at > current_time.replace(tzinfo=None)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    return expires_at > current_time


def parse_login_name(value: str) -> tuple[str, str | None]:
    """Split "name" or the legacy "name:manager" / "name:staff" form.

    Usernames are unique across the platform, so the role suffix is optional.
    When given it must match the account's role; an unknown suffix is rejected.
    Returns ("", None) for input that cannot be a username.
    """
    parts = value.strip().split(":")
    if len(parts) == 1:
        username, role = parts[0], None
    elif len(parts) == 2:
        username, suffix = parts
        role = {"owner": "owner", "manager": "manager", "staff": "staff", "employee": "staff"}.get(
            suffix.strip().casefold(), ""
        )
        if not role:
            return "", None
    else:
        return "", None
    return username.strip().casefold(), role


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def user_info(user: User) -> dict:
    subscription = user.shop.subscriptions[-1] if user.shop.subscriptions else None
    if subscription is None:
        raise ValueError("Tài khoản chưa có gói đăng ký.")
    return {
        "id": user.id,
        "shop_id": user.shop_id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "full_name": user.full_name,
        "role": {value: key for key, value in STORAGE_ROLES.items()}[user.role],
        "shop_name": user.shop.name,
        "plan": subscription.plan,
        "subscription_expires_at": subscription.subscription_expires_at,
    }


def create_user(
    db: Session,
    *,
    shop: Shop,
    username: str,
    full_name: str,
    password: str,
    role: str,
    email: str | None = None,
) -> User:
    user = User(
        shop_id=shop.id,
        full_name=full_name.strip(),
        username=normalize_username(username),
        email=email.strip().casefold() if email else None,
        phone=None,
        password_hash=hash_password(password),
        role=STORAGE_ROLES[role],
        status="ACTIVE",
        created_at=utcnow(),
    )
    db.add(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    login_value = username.strip()
    if "@" in login_value:
        users = db.scalars(
            select(User).where(func.lower(User.email) == login_value.casefold())
        ).all()
        # Do not guess if legacy data has the same email on multiple accounts.
        user = users[0] if len(users) == 1 else None
    else:
        normalized_username, role = parse_login_name(login_value)
        user = None
        if normalized_username:
            # Compare case-insensitively in SQL so the result does not depend on
            # the column collation (TiDB defaults to utf8mb4_bin).
            matches = db.scalars(
                select(User).where(func.lower(User.username) == normalized_username).limit(2)
            ).all()
            # Legacy rows that differ only by case are ambiguous: refuse to guess.
            user = matches[0] if len(matches) == 1 else None
        if user is not None and role is not None and user.role != STORAGE_ROLES[role]:
            user = None
    if (
        user is None
        or user.status != "ACTIVE"
        or not subscription_is_active(user.shop)
        or not verify_password(password, user.password_hash)
    ):
        return None

    return user


def _issue_session(db: Session, user: User, remember_me: bool) -> dict:
    now = utcnow()
    duration_seconds = (
        config.REMEMBERED_SESSION_TTL_SECONDS
        if remember_me
        else config.SESSION_TTL_SECONDS
    )
    expires_at = (now + timedelta(seconds=duration_seconds)).replace(tzinfo=None)
    session_id = str(uuid4())
    refresh_token, refresh_hash = create_refresh_token(remember_me)
    access_token, access_expires_at = create_access_token(user.id, session_id)
    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            revoked=False,
        )
    )
    db.commit()
    return {
        "access_token": access_token,
        "expires_at": datetime.fromtimestamp(access_expires_at, timezone.utc),
        "refresh_token": refresh_token,
        "refresh_expires_at": expires_at,
        "remember_me": remember_me,
        "user": user_info(user),
    }


def start_session(db: Session, user: User, remember_me: bool) -> dict:
    return _issue_session(db, user, remember_me)


def rotate_refresh_session(db: Session, refresh_token: str) -> dict | None:
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_access_token(refresh_token)
        )
    )
    if session is None:
        return None

    if session.revoked:
        # A rotated token was presented again. Revoke the account's active
        # sessions so a stolen token cannot keep using the same account.
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == session.user_id, AuthSession.revoked.is_(False))
            .values(revoked=True)
        )
        db.commit()
        return None

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    user = session.user
    if (
        expires_at <= utcnow()
        or user.status != "ACTIVE"
        or not subscription_is_active(user.shop)
    ):
        session.revoked = True
        db.commit()
        return None

    remember_me = refresh_token_is_persistent(refresh_token)
    claimed = db.execute(
        update(AuthSession)
        .where(AuthSession.id == session.id, AuthSession.revoked.is_(False))
        .values(revoked=True)
    )
    if claimed.rowcount != 1:
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == session.user_id, AuthSession.revoked.is_(False))
            .values(revoked=True)
        )
        db.commit()
        return None
    result = _issue_session(db, user, remember_me)
    return result

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import AuthSession, Shop, StoreSubscription, User


SESSION_DURATION = timedelta(hours=12)
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


def parse_login_name(value: str) -> tuple[str, str]:
    parts = value.strip().split(":")
    if len(parts) == 1:
        username, role = parts[0], "owner"
    elif len(parts) == 2:
        username, suffix = parts
        role = {"manager": "manager", "staff": "staff"}.get(suffix.casefold(), "")
    else:
        return "", ""
    return username.casefold(), role


def user_info(user: User) -> dict:
    subscription = user.shop.subscriptions[-1] if user.shop.subscriptions else None
    if subscription is None:
        raise ValueError("Tài khoản chưa có gói đăng ký.")
    return {
        "id": user.id,
        "shop_id": user.shop_id,
        "username": user.username,
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
) -> User:
    user = User(
        shop_id=shop.id,
        full_name=full_name.strip(),
        username=username.strip(),
        email=None,
        phone=None,
        password_hash=hash_password(password),
        role=STORAGE_ROLES[role],
        status="ACTIVE",
        created_at=utcnow(),
    )
    db.add(user)
    return user


def authenticate(db: Session, username: str, password: str):
    normalized_username, role = parse_login_name(username)
    user = db.scalar(
        select(User).where(
            User.username == normalized_username,
            User.role == STORAGE_ROLES.get(role, ""),
        )
    ) if normalized_username and role else None
    if (
        user is None
        or user.status != "ACTIVE"
        or not subscription_is_active(user.shop)
        or not verify_password(password, user.password_hash)
    ):
        return None

    token, token_hash = create_access_token()
    expires_at = utcnow() + SESSION_DURATION
    if expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)
    db.add(
        AuthSession(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
    )
    db.commit()
    return {"access_token": token, "expires_at": expires_at, "user": user_info(user)}
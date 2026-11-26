import calendar
import secrets
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing_extensions import Annotated
from typing import Literal

from app.core import config
from app.core.security import hash_password
from app.db.session import get_db
from app.modules.auth.models import AuthSession, Shop, StoreSubscription, User
from app.modules.auth.schemas import EmailAddress, Username
from app.modules.auth.service import create_user, subscription_is_active, utcnow


router = APIRouter(prefix="/admin", tags=["platform-admin"])
ShopName = Annotated[str, StringConstraints(min_length=2, max_length=150, strip_whitespace=True)]


class ProvisionAccountRequest(BaseModel):
    shop_name: ShopName
    # Advanced plans are temporarily unavailable for new platform-admin accounts.
    plan: Literal["basic"]
    subscription_months: int = Field(ge=1, le=36)
    owner_username: Username
    owner_email: EmailAddress
    owner_full_name: str = Field(min_length=1, max_length=150, strip_whitespace=True)
    owner_password: str = Field(min_length=12, max_length=128)


class UpdateAccountRequest(BaseModel):
    shop_name: ShopName
    plan: Literal["basic", "pro", "enterprise"]
    subscription_expires_at: date
    subscription_status: Literal["ACTIVE", "CANCELLED"]
    owner_username: Username
    owner_email: EmailAddress
    owner_full_name: str = Field(min_length=1, max_length=150, strip_whitespace=True)
    owner_password: str | None = Field(default=None, min_length=12, max_length=128)


class ProvisionedAccount(BaseModel):
    shop_id: int
    shop_name: str
    owner_username: str | None
    owner_email: str | None
    owner_full_name: str | None = None
    plan: str | None
    status: str
    subscription_status: str | None = None
    subscription_expires_at: datetime | None
    created_at: datetime


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if len(config.ADMIN_TOKEN) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mã quản trị cần được cấu hình với ít nhất 32 ký tự.",
        )
    # Copy/paste of the token often carries a trailing newline or spaces.
    supplied = (x_admin_token or "").strip()
    if not supplied or not secrets.compare_digest(supplied.encode(), config.ADMIN_TOKEN.strip().encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mã quản trị không hợp lệ.")


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


@router.post(
    "/accounts",
    response_model=ProvisionedAccount,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_token)],
)
def provision_account(payload: ProvisionAccountRequest, db: Session = Depends(get_db)):
    # Usernames are compared case-insensitively at login, so reject case-only duplicates
    # even where the column collation is case-sensitive (TiDB utf8mb4_bin).
    if db.scalar(select(User.id).where(func.lower(User.username) == payload.owner_username.casefold())):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tên đăng nhập chủ cửa hàng đã được sử dụng.",
        )
    if payload.owner_email is not None:
        duplicate_email = db.scalar(
            select(User.id).where(func.lower(User.email) == payload.owner_email.casefold())
        )
        if duplicate_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email \u0111\u00e3 \u0111\u01b0\u1ee3c d\u00f9ng cho t\u00e0i kho\u1ea3n kh\u00e1c.",
            )

    now = utcnow()
    shop = Shop(
        name=payload.shop_name,
        created_at=now,
        updated_at=now,
    )
    db.add(shop)
    db.flush()
    subscription = StoreSubscription(
        store_id=shop.id,
        plan=payload.plan,
        status="ACTIVE",
        subscription_expires_at=add_months(now, payload.subscription_months),
        created_at=now,
    )
    db.add(subscription)
    owner = create_user(
        db,
        shop=shop,
        username=payload.owner_username,
        full_name=payload.owner_full_name,
        password=payload.owner_password,
        role="owner",
        email=payload.owner_email,
    )
    try:
        db.flush()
        shop.owner_user_id = owner.id
        db.commit()
        db.refresh(shop)
        db.refresh(owner)
        db.refresh(subscription)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập chủ cửa hàng đã được sử dụng.")
    return ProvisionedAccount(
        shop_id=shop.id,
        shop_name=shop.name,
        owner_username=owner.username,
        owner_email=owner.email,
        owner_full_name=owner.full_name,
        plan=subscription.plan,
        status="active",
        subscription_status=subscription.status,
        subscription_expires_at=subscription.subscription_expires_at,
        created_at=shop.created_at,
    )


@router.patch(
    "/accounts/{shop_id}",
    response_model=ProvisionedAccount,
    dependencies=[Depends(require_admin_token)],
)
def update_account(
    shop_id: int,
    payload: UpdateAccountRequest,
    db: Session = Depends(get_db),
):
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cửa hàng.")

    owner = db.scalar(
        select(User).where(User.shop_id == shop.id, User.role == "OWNER")
    )
    subscription = shop.subscriptions[-1] if shop.subscriptions else None
    if owner is None or subscription is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cửa hàng thiếu tài khoản chủ hoặc gói đăng ký.",
        )

    username = payload.owner_username.casefold()
    duplicate_username = db.scalar(
        select(User.id).where(
            func.lower(User.username) == username,
            User.id != owner.id,
        )
    )
    if duplicate_username is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tên đăng nhập này đã được sử dụng.",
        )

    duplicate_email = db.scalar(
        select(User.id).where(
            func.lower(User.email) == payload.owner_email,
            User.id != owner.id,
        )
    )
    if duplicate_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được dùng cho tài khoản khác.",
        )

    credentials_changed = (
        owner.username != username
        or owner.email != payload.owner_email
        or payload.owner_password is not None
    )
    subscription_changed = (
        subscription.status != payload.subscription_status
        or subscription.subscription_expires_at.date() != payload.subscription_expires_at
    )
    shop.name = payload.shop_name
    shop.updated_at = utcnow()
    owner.username = username
    owner.email = payload.owner_email
    owner.full_name = payload.owner_full_name
    subscription.plan = payload.plan
    subscription.status = payload.subscription_status
    subscription.subscription_expires_at = datetime.combine(
        payload.subscription_expires_at, time.max
    )
    if payload.owner_password is not None:
        owner.password_hash = hash_password(payload.owner_password)
    if credentials_changed or subscription_changed:
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == owner.id, AuthSession.revoked.is_(False))
            .values(revoked=True)
        )

    try:
        db.commit()
        db.refresh(shop)
        db.refresh(owner)
        db.refresh(subscription)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tên đăng nhập hoặc email đã được sử dụng.",
        )
    return _account_info(shop)


@router.get(
    "/accounts",
    response_model=list[ProvisionedAccount],
    dependencies=[Depends(require_admin_token)],
)
def list_accounts(db: Session = Depends(get_db)):
    shops = db.scalars(select(Shop).order_by(Shop.created_at.desc())).all()
    return [
        _account_info(shop)
        for shop in shops
    ]


def _account_info(shop: Shop) -> ProvisionedAccount:
    subscription = shop.subscriptions[-1] if shop.subscriptions else None
    owner = next((user for user in shop.users if user.role == "OWNER"), None)
    is_active = subscription_is_active(shop)
    return ProvisionedAccount(
        shop_id=shop.id,
        shop_name=shop.name,
        owner_username=owner.username if owner else None,
        owner_email=owner.email if owner else None,
        owner_full_name=owner.full_name if owner else None,
        plan=subscription.plan if subscription else None,
        status="active" if is_active else "inactive",
        subscription_status=subscription.status if subscription else None,
        subscription_expires_at=(
            subscription.subscription_expires_at if subscription else None
        ),
        created_at=shop.created_at,
    )

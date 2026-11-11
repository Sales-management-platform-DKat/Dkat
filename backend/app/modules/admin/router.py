import calendar
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing_extensions import Annotated
from typing import Literal

from app.core import config
from app.db.session import get_db
from app.modules.auth.models import Shop, StoreSubscription, User
from app.modules.auth.schemas import Username
from app.modules.auth.service import create_user, subscription_is_active, utcnow


router = APIRouter(prefix="/admin", tags=["platform-admin"])
ShopName = Annotated[str, StringConstraints(min_length=2, max_length=150, strip_whitespace=True)]


class ProvisionAccountRequest(BaseModel):
    shop_name: ShopName
    plan: Literal["basic", "pro", "enterprise"]
    subscription_months: int = Field(ge=1, le=36)
    owner_username: Username
    owner_full_name: str = Field(min_length=1, max_length=150, strip_whitespace=True)
    owner_password: str = Field(min_length=12, max_length=128)


class ProvisionedAccount(BaseModel):
    shop_id: int
    shop_name: str
    owner_username: str | None
    plan: str | None
    status: str
    subscription_expires_at: datetime | None
    created_at: datetime


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if len(config.ADMIN_TOKEN) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mã quản trị cần được cấu hình với ít nhất 32 ký tự.",
        )
    if x_admin_token is None or not secrets.compare_digest(x_admin_token, config.ADMIN_TOKEN):
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
        plan=subscription.plan,
        status="active",
        subscription_expires_at=subscription.subscription_expires_at,
        created_at=shop.created_at,
    )


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
        plan=subscription.plan if subscription else None,
        status="active" if is_active else "inactive",
        subscription_expires_at=(
            subscription.subscription_expires_at if subscription else None
        ),
        created_at=shop.created_at,
    )

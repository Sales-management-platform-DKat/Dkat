"""The signed-in user's own store: read by every role, renamed by the OWNER only."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user, require_roles
from app.db.session import get_db
from app.modules.auth.models import Shop, User
from app.modules.auth.service import utcnow
from app.modules.stores.schemas import StoreOut, StoreUpdate

router = APIRouter(prefix="/stores", tags=["stores"])


def _store_out(db: Session, user: User) -> StoreOut:
    shop: Shop = user.shop
    subscription = shop.subscriptions[-1] if shop.subscriptions else None
    # Raw SQL on purpose: the legacy Branch ORM model is not part of Base.metadata.
    branch_rows = db.execute(
        text("SELECT status, COUNT(*) FROM branches WHERE store_id = :store GROUP BY status"), {"store": shop.id}
    ).all()
    branch_counts = {status: count for status, count in branch_rows}
    staff_count = db.scalar(
        select(func.count()).select_from(User).where(
            User.shop_id == shop.id, User.role != "OWNER", User.status == "ACTIVE"
        )
    ) or 0
    return StoreOut(
        store_id=shop.id,
        name=shop.name,
        plan=subscription.plan if subscription else None,
        subscription_status=subscription.status if subscription else None,
        subscription_expires_at=subscription.subscription_expires_at if subscription else None,
        created_at=shop.created_at,
        branch_count=sum(branch_counts.values()),
        active_branch_count=branch_counts.get("ACTIVE", 0),
        staff_count=staff_count,
        can_edit=user.role == "OWNER" and shop.owner_user_id == user.id,
    )


@router.get("/me", response_model=StoreOut, response_model_by_alias=True)
def get_my_store(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StoreOut:
    return _store_out(db, user)


@router.put("/me", response_model=StoreOut, response_model_by_alias=True)
def update_my_store(
    body: StoreUpdate,
    user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> StoreOut:
    shop = db.scalar(select(Shop).where(Shop.id == user.shop_id).with_for_update())
    shop.name = body.name
    shop.updated_at = utcnow()
    db.commit()
    db.refresh(user)
    return _store_out(db, user)

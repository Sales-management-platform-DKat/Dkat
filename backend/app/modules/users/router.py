from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate, UserInfo
from app.modules.auth.service import create_user, user_info


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
def add_store_user(
    payload: UserCreate,
    owner: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    duplicate = db.scalar(
        select(User.id).where(
            User.username == payload.username.casefold(),
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập này đã được sử dụng.")

    user = create_user(
        db,
        shop=owner.shop,
        username=payload.username,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
    )
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập này đã được sử dụng.")
    return user_info(user)
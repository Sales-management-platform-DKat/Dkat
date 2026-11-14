from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
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

    if payload.email is not None:
        duplicate_email = db.scalar(
            select(User.id).where(func.lower(User.email) == payload.email.casefold())
        )
        if duplicate_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email \u0111\u00e3 \u0111\u01b0\u1ee3c d\u00f9ng cho t\u00e0i kho\u1ea3n kh\u00e1c.",
            )

    user = create_user(
        db,
        shop=owner.shop,
        username=payload.username,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        email=payload.email,
    )
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập này đã được sử dụng.")
    return user_info(user)

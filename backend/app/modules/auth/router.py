from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.core.security import hash_access_token
from app.db.session import get_db
from app.modules.auth.models import AuthSession, User
from app.modules.auth.schemas import LoginRequest, LoginResponse, UserInfo
from app.modules.auth.service import authenticate, user_info


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = authenticate(db, payload.username, payload.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác, hoặc tài khoản đã hết hạn.",
        )
    return result


@router.get("/me", response_model=UserInfo)
def get_profile(user: User = Depends(get_current_user)):
    return user_info(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_access_token(credentials.credentials),
                AuthSession.revoked.is_(False),
            )
        )
        if session is not None:
            session.revoked = True
            db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
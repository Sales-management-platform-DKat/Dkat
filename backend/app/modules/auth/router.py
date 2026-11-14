
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.permissions import CurrentUser, require_auth
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schemas import AuthUserOut, ChangePasswordIn, LoginIn, LoginOut
from app.utils.response import SuccessResponse, ok

router = APIRouter(prefix="/auth", tags=["auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=SuccessResponse[LoginOut], response_model_by_alias=True)
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Đăng nhập: trả JWT (hạn 8 giờ) và thông tin user. 401 INVALID_CREDENTIALS / 403 ACCOUNT_LOCKED."""
    return ok(await service.login(db, body, _ip(request)))


@router.get("/me", response_model=SuccessResponse[AuthUserOut], response_model_by_alias=True)
async def me(user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """Thông tin user hiện tại (frontend gọi để khôi phục phiên khi tải lại trang)."""
    return ok(await service.get_me(db, user))


@router.post("/logout")
async def logout(request: Request, user: CurrentUser = Depends(require_auth)):
    """Ghi log đăng xuất. Token do client tự xóa (JWT không lưu phía server)."""
    service.logout(user, _ip(request))
    return ok(None)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    request: Request,
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
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

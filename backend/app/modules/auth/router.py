from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.core.permissions import get_current_user
from app.core.security import decode_access_token, hash_access_token
from app.db.session import get_db
from app.modules.auth.models import AuthSession, User
from app.modules.auth.schemas import LoginRequest, LoginResponse, UserInfo
from app.modules.auth.service import (
    authenticate,
    rotate_refresh_session,
    start_session,
    user_info,
)


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
REFRESH_COOKIE = "dkat_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _secure_cookie(request: Request) -> bool:
    if config.COOKIE_SECURE in {"1", "true", "yes", "on"}:
        return True
    if config.COOKIE_SECURE in {"0", "false", "no", "off"}:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    origin_is_https = request.headers.get("origin", "").casefold().startswith("https://")
    return request.url.scheme == "https" or forwarded_proto == "https" or origin_is_https


def _set_refresh_cookie(response: Response, request: Request, result: dict) -> None:
    expires_at = result["refresh_expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    max_age = None
    if result["remember_me"]:
        max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=result["refresh_token"],
        max_age=max_age,
        httponly=True,
        secure=_secure_cookie(request),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_secure_cookie(request),
        samesite="lax",
    )


def _public_session(result: dict) -> dict:
    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
        "expires_at": result["expires_at"],
        "user": result["user"],
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = authenticate(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác, hoặc tài khoản đã hết hạn.",
        )
    result = start_session(db, user, payload.remember_me)
    _set_refresh_cookie(response, request, result)
    return _public_session(result)


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: Request, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        response = JSONResponse(
            {"detail": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        _clear_refresh_cookie(response, request)
        return response

    result = rotate_refresh_session(db, refresh_token)
    if result is None:
        response = JSONResponse(
            {"detail": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        _clear_refresh_cookie(response, request)
        return response

    response = JSONResponse(jsonable_encoder(_public_session(result)))
    _set_refresh_cookie(response, request, result)
    return response


@router.get("/me", response_model=UserInfo)
def get_profile(user: User = Depends(get_current_user)):
    return user_info(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    changed = False
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_access_token(refresh_token)
            )
        )
        if session is not None and not session.revoked:
            session.revoked = True
            changed = True

    if credentials is not None:
        claims = decode_access_token(credentials.credentials)
        if claims is not None:
            session = db.get(AuthSession, claims["sid"])
            if session is not None and not session.revoked:
                session.revoked = True
                changed = True

    if changed:
        db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response, request)
    return response

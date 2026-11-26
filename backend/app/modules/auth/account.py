"""Self-service for the signed-in user: profile, password and sessions (Settings screen).

Errors use 400/409 with {"code", "message"} details; never 401, because the web client treats 401 as an
expired session and signs the user out.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.permissions import bearer_scheme, get_current_user
from app.core.security import decode_access_token, hash_password, verify_password
from app.db.session import get_db
from app.modules.auth.models import AuthSession, User
from app.modules.auth.schemas import EmailAddress, UserInfo
from app.modules.auth.service import user_info, utcnow

router = APIRouter(prefix="/auth", tags=["account"])
PHONE_PATTERN = r"^\+?[0-9][0-9 .-]{7,18}$"


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailAddress | None = None
    phone: str | None = Field(default=None, max_length=20, pattern=PHONE_PATTERN)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class SessionSummary(BaseModel):
    active_sessions: int
    other_sessions: int


class RevokeResult(BaseModel):
    revoked_sessions: int


def _error(code: int, key: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": key, "message": message})


def current_session_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    # get_current_user (also a dependency of every route here) has already validated this token.
    claims = decode_access_token(credentials.credentials) if credentials else None
    return claims["sid"] if claims else ""


def _live_sessions(user_id: int):
    return (AuthSession.user_id == user_id, AuthSession.revoked.is_(False),
            AuthSession.expires_at > utcnow().replace(tzinfo=None))


def _revoke_others(db: Session, user_id: int, keep_session_id: str) -> int:
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked.is_(False), AuthSession.id != keep_session_id)
        .values(revoked=True)
    )
    return result.rowcount or 0


@router.put("/me", response_model=UserInfo)
def update_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.email and db.scalar(
        select(User.id).where(func.lower(User.email) == payload.email, User.id != user.id)
    ):
        raise _error(status.HTTP_409_CONFLICT, "EMAIL_TAKEN", "Email đã được dùng cho tài khoản khác.")
    user.full_name = payload.full_name
    user.email = payload.email
    user.phone = payload.phone
    db.commit()
    db.refresh(user)
    return user_info(user)


@router.post("/change-password", response_model=RevokeResult)
def change_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    session_id: str = Depends(current_session_id),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise _error(status.HTTP_400_BAD_REQUEST, "CURRENT_PASSWORD_INVALID", "Mật khẩu hiện tại không đúng.")
    if verify_password(payload.new_password, user.password_hash):
        raise _error(status.HTTP_400_BAD_REQUEST, "PASSWORD_UNCHANGED", "Mật khẩu mới phải khác mật khẩu hiện tại.")
    user.password_hash = hash_password(payload.new_password)
    # Anyone holding an old session (stolen or forgotten device) is signed out; this device stays signed in.
    revoked = _revoke_others(db, user.id, session_id)
    db.commit()
    return RevokeResult(revoked_sessions=revoked)


@router.get("/sessions", response_model=SessionSummary)
def session_summary(user: User = Depends(get_current_user), session_id: str = Depends(current_session_id),
                    db: Session = Depends(get_db)):
    active = db.scalar(select(func.count()).select_from(AuthSession).where(*_live_sessions(user.id))) or 0
    return SessionSummary(active_sessions=active, other_sessions=max(active - 1, 0) if session_id else active)


@router.post("/sessions/revoke-others", response_model=RevokeResult)
def revoke_other_sessions(user: User = Depends(get_current_user), session_id: str = Depends(current_session_id),
                          db: Session = Depends(get_db)):
    revoked = _revoke_others(db, user.id, session_id)
    db.commit()
    return RevokeResult(revoked_sessions=revoked)

"""Password hashing (bcrypt) and JWT access tokens."""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

# bcrypt only uses the first 72 bytes; longer inputs are rejected instead of silently truncated
BCRYPT_MAX_BYTES = 72
_MIN_ROUNDS = 10


def _rounds() -> int:
    return max(settings.BCRYPT_ROUNDS, _MIN_ROUNDS)


def _hash_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_rounds())).decode("ascii")


def _verify_sync(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("ascii"))
    except ValueError:  # malformed hash in DB
        return False


# Used when the username does not exist, so the response time matches a real check
# (prevents finding valid usernames by timing).
_DUMMY_HASH = _hash_sync("dkat-dummy-password")


async def hash_password(password: str) -> str:
    """bcrypt is CPU-heavy (~0.2 s at cost 12): run it off the event loop."""
    return await run_in_threadpool(_hash_sync, password)


async def verify_password(password: str, password_hash: str | None) -> bool:
    """Pass password_hash=None when the user does not exist: still spends the bcrypt time, always False."""
    matched = await run_in_threadpool(_verify_sync, password, password_hash or _DUMMY_HASH)
    return matched and password_hash is not None


def create_access_token(*, user_id: int, role: str, store_id: int, branch_ids: list[int]) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "user_id": user_id,
        "role": role,
        "store_id": store_id,
        "branch_ids": branch_ids,
        "iat": now,
        "exp": now + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raise jwt.PyJWTError (expired, bad signature, malformed...) if the token is invalid."""
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )

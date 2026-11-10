import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


@dataclass(frozen=True)
class Actor:
    store_id: int
    role: str
    user_id: int


def require_auth(request: Request) -> Actor:
    # Local development adapter. Replace with the team's authenticated principal.
    user_id = os.getenv("DKAT_DEV_USER_ID", "")
    if (
        request.client is None
        or request.client.host not in {"127.0.0.1", "::1"}
        or not user_id.isascii()
        or not user_id.isdecimal()
        or len(user_id) > 19
        or not 0 < int(user_id) <= 9223372036854775807
    ):
        raise HTTPException(401, "Authentication required")

    try:
        with engine.connect() as db:
            user = db.execute(
                text("SELECT store_id, role FROM users WHERE user_id = :id AND status = 'ACTIVE'"),
                {"id": int(user_id)},
            ).mappings().one_or_none()
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    if user is None:
        raise HTTPException(401, "Authentication required")
    return Actor(user["store_id"], user["role"], int(user_id))


def require_owner(actor: Annotated[Actor, Depends(require_auth)]) -> Actor:
    if actor.role != "OWNER":
        raise HTTPException(403, "OWNER role required")
    return actor

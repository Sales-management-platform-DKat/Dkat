import hashlib
import json
import math

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.session import engine
from app.modules.preorders.errors import PreorderError

LIMIT = 5
WINDOW_SECONDS = 600


def consume_request(db: Connection, ip: str) -> None:
    """A rolling window shared by all workers; the IP row serializes concurrent attempts."""
    key = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    db.execute(
        text("""
            INSERT INTO preorder_request_limits (ip_key, request_times) VALUES (:key, '[]')
            ON DUPLICATE KEY UPDATE ip_key = ip_key
        """), {"key": key},
    )
    stored = db.execute(
        text("SELECT request_times FROM preorder_request_limits WHERE ip_key=:key FOR UPDATE"),
        {"key": key},
    ).scalar_one()
    now = float(db.execute(text("SELECT UNIX_TIMESTAMP(UTC_TIMESTAMP(6))")).scalar_one())
    attempts = json.loads(stored) if isinstance(stored, str) else stored
    attempts = [stamp for stamp in attempts if stamp > now - WINDOW_SECONDS]
    if len(attempts) >= LIMIT:
        retry_after = max(1, math.ceil(WINDOW_SECONDS - (now - min(attempts))))
        raise PreorderError(429, "RATE_LIMIT_EXCEEDED", "Chỉ được gửi 5 yêu cầu trong 10 phút mỗi IP",
                            headers={"Retry-After": str(retry_after)})
    db.execute(
        text("UPDATE preorder_request_limits SET request_times=:times WHERE ip_key=:key"),
        {"key": key, "times": json.dumps([*attempts, now])},
    )


def limit_preorder_requests(request: Request) -> None:
    # Read the ASGI peer address; never trust arbitrary X-Forwarded-For headers here.
    ip = request.client.host if request.client else "unknown"
    # This short transaction is separate so failed orders still consume a request.
    with engine.begin() as db:
        consume_request(db, ip)

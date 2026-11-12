from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends

from app.core.permissions import require_role
from app.db.session import ping_database
from app.modules.health import service
from app.utils.response import ok

router = APIRouter(prefix="/health", tags=["health"])

_started = time.monotonic()


@router.get("")
async def health_check():
    """Always 200 while the server is alive; `database` reports the MySQL connection status."""
    db_up = await ping_database()
    return ok(
        {
            "status": "ok",
            "uptime": round(time.monotonic() - _started),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "up" if db_up else "down",
        }
    )


@router.get("/db", dependencies=[Depends(require_role("OWNER"))])
async def database_check():
    """Detailed DB connection check: 200 if connected, 503 DATABASE_UNAVAILABLE if not.

    Returns: DB name, MySQL version, latency, charset, table list and whether all 18 tables exist.
    OWNER only (401 without token, 403 FORBIDDEN for MANAGER/EMPLOYEE).
    """
    return ok(await service.check_database())

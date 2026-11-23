"""Audit trail for access to personal data (NFR-08).

One JSON object per line in settings.CUSTOMER_ACCESS_LOG_FILE (default logs/customer_access.log,
relative to backend/), rotated at 5 MB, 10 files kept:

    {"time": "2026-11-24T03:12:45.123+00:00", "event": "CUSTOMER_VIEW", "userId": 3, "role": "EMPLOYEE",
     "storeId": 1, "customerId": 42, "ip": "127.0.0.1"}

Only ids are written, never the customer's name, phone or email. The file is the record:
this logger does not propagate to the console log.
"""
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

_logger = logging.getLogger("app.audit.customer_access")
_logger.propagate = False
_logger.setLevel(logging.INFO)


def _ensure_handler() -> None:
    path = Path(settings.CUSTOMER_ACCESS_LOG_FILE)
    target = str(path.resolve())
    if any(getattr(h, "baseFilename", None) == target for h in _logger.handlers):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)


def log_customer_view(*, user_id: int, role: str, store_id: int, customer_id: int, ip: str | None) -> None:
    """Who viewed which customer, and when."""
    _ensure_handler()
    _logger.info(
        json.dumps(
            {
                "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "event": "CUSTOMER_VIEW",
                "userId": user_id,
                "role": role,
                "storeId": store_id,
                "customerId": customer_id,
                "ip": ip,
            }
        )
    )

import logging

from app.modules.preorders.services.allocation import allocate_imported_preorders
from app.modules.preorders.services.notifications import notify_ready_preorders

logger = logging.getLogger(__name__)


def process_committed_stock_import(branch_id: int, variant_ids: list[int]) -> None:
    """Allocate and notify after the stock import (JSON or CSV) has committed."""
    try:
        ready_ids = allocate_imported_preorders(branch_id, variant_ids)
    except Exception:
        logger.exception("Preorder allocation failed after import committed for branch %s", branch_id)
        return

    notify_ready_preorders(ready_ids)

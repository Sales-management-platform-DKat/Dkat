import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine
from app.modules.preorders.services.allocation import AllocationInvariantError
from app.modules.preorders.services.lifecycle import expire_preorder
from app.modules.preorders.services.notifications import notify_ready_preorders

logger = logging.getLogger(__name__)
RUN_INTERVAL_SECONDS = 3600
BATCH_SIZE = 100


def expire_due_preorders() -> int:
    """Expire a snapshot of due orders in independent, retryable transactions."""
    with engine.connect() as db:
        cutoff = db.execute(text("SELECT UTC_TIMESTAMP()")).scalar_one()
    last_id = expired_count = 0
    transaction_engine = engine.execution_options(isolation_level="READ COMMITTED")
    while True:
        with engine.connect() as db:
            batch = db.execute(text("""
                SELECT preorder_id, branch_id FROM preorders
                WHERE preorder_id>:last_id AND status IN ('READY','NOTIFIED') AND expires_at < :cutoff
                ORDER BY preorder_id LIMIT :size
            """), {"last_id": last_id, "cutoff": cutoff, "size": BATCH_SIZE}).all()
        for preorder_id, branch_id in batch:
            try:
                with transaction_engine.begin() as db:
                    ready_ids = expire_preorder(db, branch_id, preorder_id, cutoff)
            except (SQLAlchemyError, AllocationInvariantError):
                logger.exception("Could not expire preorder %s; eligible for retry on the next run", preorder_id)
                continue
            if ready_ids is not None:
                expired_count += 1
                notify_ready_preorders(ready_ids)
        if len(batch) < BATCH_SIZE:
            return expired_count
        last_id = batch[-1].preorder_id


async def run_preorder_expiry(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=RUN_INTERVAL_SECONDS)
            return
        except TimeoutError:
            pass
        try:
            expired_count = await asyncio.to_thread(expire_due_preorders)
            logger.info("Expired %s preorders", expired_count)
        except Exception:
            logger.exception("Preorder expiry pass failed")


if __name__ == "__main__":
    print(f"Expired preorders: {expire_due_preorders()}")

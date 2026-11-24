"""Minimal access audit for customer PII reads; never records contact values."""
import logging

logger = logging.getLogger("dkat.customer_access")


def log_customer_access(*, store_id: int, user_id: int, action: str, customer_ids: list[int], ip: str | None) -> None:
    logger.info(
        "customer_access store_id=%s user_id=%s action=%s customer_ids=%s ip=%s",
        store_id, user_id, action, ",".join(str(value) for value in customer_ids[:100]), ip or "unknown",
    )

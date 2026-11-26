"""Default branch bootstrap for store owners.

Inventory, stock import and POS all need a valid branch_id. A store provisioned through the
platform admin has no branch yet, so the first owner login creates one ("Chi nhánh chính").

Guarantees:
- Only the OWNER recorded in stores.owner_user_id triggers creation; managers, staff and the
  platform admin (token based, no user row) never create branches.
- Idempotent: a store that already has any branch (ACTIVE or INACTIVE) is left untouched, so an
  owner who deliberately deactivated every branch does not get a new one behind their back.
- Concurrency safe: the store row is locked (SELECT ... FOR UPDATE) before checking, and the
  (store_id, branch_code) unique key rejects a duplicate that slips through anyway.
- The branch insert and its inventory rows commit together or roll back together.
"""
import logging
from typing import Literal

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.auth.models import Shop, User

logger = logging.getLogger(__name__)

BranchSetup = Literal["existing", "created", "inactive", "failed", "not_applicable"]
DEFAULT_BRANCH_CODE = "CN01"
DEFAULT_BRANCH_NAMES = {"vi": "Chi nhánh chính", "en": "Main Branch"}


def default_branch_name(locale: str | None) -> str:
    return DEFAULT_BRANCH_NAMES.get((locale or "vi").split("-")[0].lower(), DEFAULT_BRANCH_NAMES["vi"])


def create_zero_inventory_rows(db, branch_id: int, store_id: int) -> int:
    """Insert quantity-0 inventory rows for every ACTIVE variant of the store that the branch lacks."""
    return db.execute(
        text("""
            INSERT INTO inventory (branch_id, variant_id, quantity)
            SELECT :branch_id, v.variant_id, 0
            FROM product_variants v
            JOIN products p ON p.product_id = v.product_id
            LEFT JOIN inventory i ON i.branch_id = :branch_id AND i.variant_id = v.variant_id
            WHERE p.store_id = :store_id AND v.status = 'ACTIVE' AND i.inventory_id IS NULL
        """),
        {"branch_id": branch_id, "store_id": store_id},
    ).rowcount or 0


def _first_branch(db: Session, store_id: int) -> tuple[int | None, bool]:
    """Return (lowest ACTIVE branch id or None, whether the store has any branch at all)."""
    rows = db.execute(
        text("SELECT branch_id, status FROM branches WHERE store_id = :store_id ORDER BY branch_id"),
        {"store_id": store_id},
    ).all()
    active = next((row.branch_id for row in rows if row.status == "ACTIVE"), None)
    return active, bool(rows)


def _free_branch_code(db: Session, store_id: int) -> str:
    used = set(db.execute(
        text("SELECT branch_code FROM branches WHERE store_id = :store_id"), {"store_id": store_id}
    ).scalars())
    if DEFAULT_BRANCH_CODE not in used:
        return DEFAULT_BRANCH_CODE
    number = 2
    while f"CN{number:02d}" in used:
        number += 1
    return f"CN{number:02d}"


def ensure_owner_default_branch(
    db: Session, user: User, locale: str | None = None
) -> tuple[int | None, BranchSetup]:
    """Make sure the owner's store has a usable branch. Commits or rolls back its own work."""
    if user.role != "OWNER":
        return None, "not_applicable"
    try:
        store_id = db.execute(
            select(Shop.id)
            .where(Shop.id == user.shop_id, Shop.owner_user_id == user.id)
            .with_for_update()
        ).scalar()
        if store_id is None:
            db.rollback()
            return None, "not_applicable"
        active_id, has_any = _first_branch(db, store_id)
        if has_any:
            db.rollback()  # release the lock; nothing to write
            return active_id, ("existing" if active_id is not None else "inactive")

        result = db.execute(
            text("""
                INSERT INTO branches (store_id, branch_code, name, address, phone, status)
                VALUES (:store_id, :code, :name, '', NULL, 'ACTIVE')
            """),
            {"store_id": store_id, "code": _free_branch_code(db, store_id), "name": default_branch_name(locale)},
        )
        branch_id = result.lastrowid
        create_zero_inventory_rows(db, branch_id, store_id)
        db.commit()
        logger.info("Created default branch %s for store %s", branch_id, store_id)
        return branch_id, "created"
    except IntegrityError:
        # Another request created the branch between our check and insert: use theirs.
        db.rollback()
        active_id, has_any = _first_branch(db, user.shop_id)
        db.rollback()
        if has_any:
            return active_id, ("existing" if active_id is not None else "inactive")
        logger.exception("Default branch creation failed for store %s", user.shop_id)
        return None, "failed"
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Default branch creation failed for store %s", user.shop_id)
        return None, "failed"

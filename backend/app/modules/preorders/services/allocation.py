from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core import config
from app.db.session import engine
from app.modules.inventory.service import lock_inventory_rows, reserved_quantities


class AllocationInvariantError(RuntimeError):
    """Existing reservations are inconsistent; abort rather than over-allocate stock."""


@dataclass(frozen=True)
class AllocationChange:
    preorder_id: int
    preorder_item_id: int
    quantity_change: int
    allocated_quantity: int


@dataclass(frozen=True)
class AllocationResult:
    branch_id: int
    variant_id: int
    quantity: int
    reserved_quantity: int
    allocated_quantity: int
    available_quantity: int
    changes: tuple[AllocationChange, ...]
    ready_preorder_ids: tuple[int, ...]


def allocate_preorders(
    db: Connection, branch_id: int, variant_id: int, *, ready_days: int | None = None,
) -> AllocationResult:
    """Allocate one variant inside the caller's READ COMMITTED transaction; never commit.

    Reservation writers must lock inventory first, then parent orders before item rows.
    For multiple variants, pre-lock all inventory rows in ascending variant_id order;
    use allocate_imported_preorders() when the caller needs a complete post-commit batch.
    """
    for value in (branch_id, variant_id):
        if type(value) is not int or not 0 < value <= 9223372036854775807:
            raise ValueError("branch_id and variant_id must be positive BIGINT IDs")
    days = config.PREORDER_READY_DAYS if ready_days is None else ready_days
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("ready_days must be an integer from 1 to 365")
    if not db.in_transaction() or db.get_isolation_level() != "READ COMMITTED":
        raise ValueError("FIFO requires an explicit READ COMMITTED transaction")

    inventory = lock_inventory_rows(db, branch_id, [variant_id], create_missing=False)
    quantity = inventory.get(variant_id, (None, 0))[1]
    reserved = reserved_quantities(db, branch_id, [variant_id]).get(variant_id, 0)
    if reserved > quantity:
        raise AllocationInvariantError("RESERVATION_EXCEEDS_STOCK")
    available = quantity - reserved
    changes, ready_ids = [], []
    if available:
        # Only discover IDs here: JOIN ... FOR UPDATE can lock children/parents in an
        # optimizer-dependent order. Take each parent explicitly in the global FIFO order.
        candidates = db.execute(text("""
            SELECT DISTINCT p.preorder_id,p.created_at
            FROM preorders AS p JOIN preorder_items AS i ON i.preorder_id=p.preorder_id
            WHERE p.branch_id=:branch AND p.status='WAITING_STOCK' AND i.variant_id=:variant
              AND i.allocated_quantity < i.quantity
            ORDER BY p.created_at ASC,p.preorder_id ASC
        """), {"branch": branch_id, "variant": variant_id}).all()
        now = db.execute(text("SELECT UTC_TIMESTAMP()")).scalar_one()
        for candidate in candidates:
            if not available:
                break
            status = db.execute(text("""
                SELECT status FROM preorders WHERE preorder_id=:id AND branch_id=:branch FOR UPDATE
            """), {"id": candidate.preorder_id, "branch": branch_id}).scalar_one_or_none()
            if status != "WAITING_STOCK":
                continue
            # Current reads after the parent lock see allocations committed by another
            # variant worker, which is essential when the last missing line becomes full.
            items = [dict(row) for row in db.execute(text("""
                SELECT preorder_item_id,variant_id,quantity,allocated_quantity FROM preorder_items
                WHERE preorder_id=:id ORDER BY preorder_item_id FOR UPDATE
            """), {"id": candidate.preorder_id}).mappings()]
            for item in items:
                if not 0 <= item["allocated_quantity"] <= item["quantity"]:
                    raise AllocationInvariantError("INVALID_ALLOCATED_QUANTITY")
                if item["variant_id"] != variant_id:
                    continue
                delta = min(item["quantity"] - item["allocated_quantity"], available)
                if delta:
                    item["allocated_quantity"] += delta
                    db.execute(text("""
                        UPDATE preorder_items SET allocated_quantity=:allocated WHERE preorder_item_id=:id
                    """), {"allocated": item["allocated_quantity"], "id": item["preorder_item_id"]})
                    available -= delta
                    changes.append(AllocationChange(candidate.preorder_id, item["preorder_item_id"], delta, item["allocated_quantity"]))
            if items and all(item["allocated_quantity"] == item["quantity"] for item in items):
                db.execute(text("""
                    UPDATE preorders SET status='READY',ready_at=:at,expires_at=:expires
                    WHERE preorder_id=:id AND status='WAITING_STOCK'
                """), {"id": candidate.preorder_id, "at": now, "expires": now + timedelta(days=days)})
                ready_ids.append(candidate.preorder_id)
    return AllocationResult(branch_id, variant_id, quantity, reserved, quantity - reserved - available,
                            available, tuple(changes), tuple(ready_ids))


def allocate_imported_preorders(branch_id: int, variant_ids: list[int]) -> list[int]:
    """Allocate committed stock and return newly READY orders after allocation commits."""
    variants = sorted(set(variant_ids))
    if not variants:
        return []
    with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
        # Acquire the entire batch before any parent-order locks, preventing inverse
        # lock order when concurrent imports provide different subsets of variants.
        lock_inventory_rows(db, branch_id, variants, create_missing=False)
        return allocate_locked_variants(db, branch_id, variants)


def allocate_locked_variants(db: Connection, branch_id: int, variant_ids: list[int]) -> list[int]:
    """Allocate specific variants after the caller has locked all their inventory rows."""
    ready_ids = []
    for variant in sorted(set(variant_ids)):
        result = allocate_preorders(db, branch_id, variant)
        ready_ids.extend(result.ready_preorder_ids)
    return list(dict.fromkeys(ready_ids))

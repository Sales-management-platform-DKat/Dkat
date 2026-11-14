"""SQL queries for branches."""
from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.models import Branch

# Pre-orders that still wait for the branch to hand over goods (BR: a branch with these cannot be closed)
OPEN_PREORDER_STATUSES = ("WAITING_STOCK", "READY", "NOTIFIED")


async def list_branches(
    db: AsyncSession, store_id: int, branch_ids: list[int] | None = None, status: str | None = None
) -> list[Branch]:
    """branch_ids=None -> every branch of the store; a list -> only those ids (empty list -> nothing)."""
    stmt = select(Branch).where(Branch.store_id == store_id)
    if branch_ids is not None:
        if not branch_ids:
            return []
        stmt = stmt.where(Branch.branch_id.in_(branch_ids))
    if status is not None:
        stmt = stmt.where(Branch.status == status)
    return list((await db.execute(stmt.order_by(Branch.branch_code))).scalars())


async def get_branch(db: AsyncSession, store_id: int, branch_id: int, *, for_update: bool = False) -> Branch | None:
    stmt = select(Branch).where(Branch.branch_id == branch_id, Branch.store_id == store_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def code_exists(db: AsyncSession, store_id: int, branch_code: str, exclude_branch_id: int | None = None) -> bool:
    # The column collation is case-insensitive, so "cn01" and "CN01" are the same code
    stmt = select(Branch.branch_id).where(Branch.store_id == store_id, Branch.branch_code == branch_code)
    if exclude_branch_id is not None:
        stmt = stmt.where(Branch.branch_id != exclude_branch_id)
    return (await db.execute(stmt.limit(1))).first() is not None


async def insert_branch(db: AsyncSession, branch: Branch) -> Branch:
    db.add(branch)
    await db.flush()
    await db.refresh(branch)  # load server defaults (created_at, status)
    return branch


async def save_branch(db: AsyncSession, branch: Branch) -> Branch:
    await db.flush()
    await db.refresh(branch)
    return branch


async def init_inventory_for_branch(db: AsyncSession, store_id: int, branch_id: int) -> int:
    """Create inventory rows with quantity 0 for every ACTIVE variant of the store that the branch
    does not have yet. Safe to call again (only missing rows are inserted). Returns rows created."""
    result = await db.execute(
        text(
            """
            INSERT INTO inventory (branch_id, variant_id, quantity)
            SELECT :branch_id, v.variant_id, 0
            FROM product_variants v
            JOIN products p ON p.product_id = v.product_id
            LEFT JOIN inventory i ON i.branch_id = :branch_id AND i.variant_id = v.variant_id
            WHERE p.store_id = :store_id AND v.status = 'ACTIVE' AND i.inventory_id IS NULL
            """
        ),
        {"branch_id": branch_id, "store_id": store_id},
    )
    return result.rowcount or 0


async def count_open_preorders(db: AsyncSession, branch_id: int) -> int:
    stmt = text("SELECT COUNT(*) FROM preorders WHERE branch_id = :b AND status IN :statuses").bindparams(
        bindparam("statuses", expanding=True)  # -> IN (:s_1, :s_2, :s_3)
    )
    result = await db.execute(stmt, {"b": branch_id, "statuses": list(OPEN_PREORDER_STATUSES)})
    return int(result.scalar_one())

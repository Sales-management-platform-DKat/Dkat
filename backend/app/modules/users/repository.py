"""SQL queries for internal user accounts."""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.models import Branch
from app.modules.users.models import User, UserBranch


async def list_store_users(db: AsyncSession, store_id: int) -> list[User]:
    stmt = select(User).where(User.store_id == store_id).order_by(User.role, User.username)
    return list((await db.execute(stmt)).scalars())


async def get_user(db: AsyncSession, store_id: int, user_id: int, *, for_update: bool = False) -> User | None:
    stmt = select(User).where(User.user_id == user_id, User.store_id == store_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def branches_by_user(db: AsyncSession, user_ids: list[int]) -> dict[int, list[Branch]]:
    """Assigned branches (any status) per user id. Users without assignment are absent from the dict."""
    if not user_ids:
        return {}
    stmt = (
        select(UserBranch.user_id, Branch)
        .join(Branch, Branch.branch_id == UserBranch.branch_id)
        .where(UserBranch.user_id.in_(user_ids))
        .order_by(Branch.branch_id)
    )
    result: dict[int, list[Branch]] = {}
    for user_id, branch in (await db.execute(stmt)).all():
        result.setdefault(user_id, []).append(branch)
    return result


async def username_exists(db: AsyncSession, username: str) -> bool:
    # Unique across the whole platform (uq_users_username); collation is case-insensitive
    return (await db.execute(select(User.user_id).where(User.username == username).limit(1))).first() is not None


async def active_branch_ids(db: AsyncSession, store_id: int, branch_ids: list[int]) -> set[int]:
    """Subset of `branch_ids` that are ACTIVE branches of the store."""
    stmt = select(Branch.branch_id).where(
        Branch.store_id == store_id, Branch.status == "ACTIVE", Branch.branch_id.in_(branch_ids)
    )
    return set((await db.execute(stmt)).scalars())


async def insert_user(db: AsyncSession, user: User, branch_ids: list[int]) -> User:
    db.add(user)
    await db.flush()
    db.add_all(UserBranch(user_id=user.user_id, branch_id=b) for b in branch_ids)
    await db.flush()
    await db.refresh(user)  # load server defaults (created_at, status)
    return user


async def save_user(db: AsyncSession, user: User) -> User:
    await db.flush()
    await db.refresh(user)
    return user


async def lock_active_owners(db: AsyncSession, store_id: int) -> int:
    """Count ACTIVE owners of the store, locking their rows so two owners cannot lock each other at once."""
    stmt = (
        select(User.user_id)
        .where(User.store_id == store_id, User.role == "OWNER", User.status == "ACTIVE")
        .with_for_update()
    )
    return len((await db.execute(stmt)).all())


async def set_password_hash(db: AsyncSession, user_id: int, password_hash: str) -> None:
    await db.execute(update(User).where(User.user_id == user_id).values(password_hash=password_hash))

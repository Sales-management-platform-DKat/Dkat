"""SQL queries for internal user accounts."""
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.models import Branch
from app.modules.users.models import User, UserBranch


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_users_page(
    db: AsyncSession,
    store_id: int,
    *,
    manager_branch_ids: list[int] | None = None,
    branch_id: int | None = None,
    role: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """One page of the store's users and the total count.

    manager_branch_ids (MANAGER scope): only EMPLOYEE accounts that have at least one ACTIVE branch
    and whose ACTIVE branches are all inside these ids. Same rule as users.service._in_manager_scope.
    branch_id: users assigned to that branch (OWNER has no assignment rows, so never matches).
    keyword: username, full name, email or phone contains it (case-insensitive collation).
    """
    stmt = select(User).where(User.store_id == store_id)
    if manager_branch_ids is not None:
        if not manager_branch_ids:
            return [], 0
        active_assignment = (
            select(UserBranch.user_branch_id)
            .join(Branch, Branch.branch_id == UserBranch.branch_id)
            .where(UserBranch.user_id == User.user_id, Branch.status == "ACTIVE")
        )
        stmt = stmt.where(
            User.role == "EMPLOYEE",
            active_assignment.exists(),
            ~active_assignment.where(UserBranch.branch_id.not_in(manager_branch_ids)).exists(),
        )
    if branch_id is not None:
        stmt = stmt.where(
            select(UserBranch.user_branch_id)
            .where(UserBranch.user_id == User.user_id, UserBranch.branch_id == branch_id)
            .exists()
        )
    if role is not None:
        stmt = stmt.where(User.role == role)
    if status is not None:
        stmt = stmt.where(User.status == status)
    if keyword:
        pattern = f"%{_escape_like(keyword)}%"
        stmt = stmt.where(
            or_(*(col.like(pattern, escape="\\") for col in (User.username, User.full_name, User.email, User.phone)))
        )

    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    page_stmt = stmt.order_by(User.role, User.username).limit(page_size).offset((page - 1) * page_size)
    return list((await db.execute(page_stmt)).scalars()), total


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


async def replace_user_branches(db: AsyncSession, user_id: int, branch_ids: set[int]) -> None:
    """Make user_branches for `user_id` equal to `branch_ids`.

    Only the difference is written: kept rows keep their assigned_at, and a (user_id, branch_id) pair
    is never inserted twice (uq_user_branch would also reject it).
    """
    current = await assigned_branch_ids(db, user_id)
    removed = current - branch_ids
    added = sorted(branch_ids - current)
    if removed:
        await db.execute(delete(UserBranch).where(UserBranch.user_id == user_id, UserBranch.branch_id.in_(removed)))
    if added:
        db.add_all(UserBranch(user_id=user_id, branch_id=b) for b in added)
    await db.flush()


async def assigned_branch_ids(db: AsyncSession, user_id: int) -> set[int]:
    return set((await db.execute(select(UserBranch.branch_id).where(UserBranch.user_id == user_id))).scalars())


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

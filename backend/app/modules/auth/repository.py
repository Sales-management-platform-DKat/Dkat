"""SQL queries for authentication."""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.models import Branch
from app.modules.users.models import User, UserBranch


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    return (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def list_user_branches(db: AsyncSession, user: User) -> list[Branch]:
    """Active branches the user may work in.

    OWNER: every branch of their store. MANAGER/EMPLOYEE: branches assigned in user_branches.
    """
    stmt = select(Branch).where(Branch.status == "ACTIVE")
    if user.role == "OWNER":
        stmt = stmt.where(Branch.store_id == user.store_id)
    else:
        stmt = stmt.join(UserBranch, UserBranch.branch_id == Branch.branch_id).where(UserBranch.user_id == user.user_id)
    return list((await db.execute(stmt.order_by(Branch.branch_id))).scalars())


async def update_password_hash(db: AsyncSession, user_id: int, password_hash: str) -> None:
    await db.execute(update(User).where(User.user_id == user_id).values(password_hash=password_hash))

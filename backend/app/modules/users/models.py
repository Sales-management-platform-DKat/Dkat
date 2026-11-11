"""Tables `users` and `user_branches` (see DKat_CSDL)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

USER_ROLES = ("OWNER", "MANAGER", "EMPLOYEE")
USER_STATUSES = ("ACTIVE", "LOCKED")


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(Enum(*USER_ROLES, name="user_role"), nullable=False)
    status: Mapped[str] = mapped_column(Enum(*USER_STATUSES, name="user_status"), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class UserBranch(Base):
    __tablename__ = "user_branches"

    user_branch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.branch_id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

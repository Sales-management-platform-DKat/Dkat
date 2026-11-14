from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Shop(Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_stores_owner"),
        ForeignKeyConstraint(
            ["store_id", "owner_user_id"],
            ["users.store_id", "users.user_id"],
            name="fk_stores_owner",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
            use_alter=True,
        ),
    )

    id: Mapped[int] = mapped_column("store_id", ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    users: Mapped[list["User"]] = relationship(
        back_populates="shop", foreign_keys="User.shop_id"
    )
    subscriptions: Mapped[list["StoreSubscription"]] = relationship(
        back_populates="shop", order_by="StoreSubscription.created_at"
    )


class StoreSubscription(Base):
    __tablename__ = "store_subscriptions"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("stores.store_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "EXPIRED", "CANCELLED", name="subscription_status"),
        nullable=False,
    )
    subscription_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    shop: Mapped[Shop] = relationship(back_populates="subscriptions")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("store_id", "user_id", name="uq_users_store_user"),
        UniqueConstraint("username", name="username"),
    )

    id: Mapped[int] = mapped_column("user_id", ID_TYPE, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        "store_id",
        ID_TYPE, ForeignKey("stores.store_id", ondelete="RESTRICT"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("OWNER", "MANAGER", "EMPLOYEE", name="user_role"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "LOCKED", name="user_status"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    shop: Mapped[Shop] = relationship(
        back_populates="users", foreign_keys=[shop_id]
    )
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="sessions")

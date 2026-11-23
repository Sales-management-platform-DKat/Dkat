"""Table `notifications` (see DKat_CSDL): one row per send attempt (SMS or EMAIL)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CHANNELS = ("SMS", "EMAIL")
STATUSES = ("PENDING", "SENT", "FAILED")


class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # FK fk_noti_preorder exists in the DB; not declared here because no ORM model maps `preorders`
    preorder_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel: Mapped[str] = mapped_column(Enum(*CHANNELS, name="notification_channel"), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Enum(*STATUSES, name="notification_status"), nullable=False, default="PENDING")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC, set when the provider accepted the message
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # database/09_notification_retry.sql
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # re-sends after the first attempt
    event_type: Mapped[str | None] = mapped_column(String(40))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC

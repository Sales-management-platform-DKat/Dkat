"""Response schemas for notification history / resend (JSON uses camelCase)."""
from datetime import datetime
from typing import Literal

from app.modules.auth.schemas import CamelModel


class NotificationOut(CamelModel):
    id: int
    preorder_id: int
    event_type: str | None
    channel: str  # SMS | EMAIL
    recipient: str  # masked: 0912***678 / n***@gmail.com (NFR-08)
    message: str
    status: str  # PENDING | SENT | FAILED
    retry_count: int  # re-sends after the first attempt
    can_resend: bool  # status == FAILED
    provider_message_id: str | None
    error_message: str | None
    sent_at: datetime | None  # UTC
    last_attempt_at: datetime | None  # UTC
    created_at: datetime


class PreorderNotificationsOut(CamelModel):
    preorder_id: int
    preorder_code: str
    max_auto_retries: int
    items: list[NotificationOut]  # oldest first


class ResendOut(CamelModel):
    result: Literal["SENT", "FAILED"]  # outcome of this re-send
    notification: NotificationOut

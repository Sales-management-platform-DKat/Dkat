"""Response bodies of the notification API (camelCase JSON, snake_case attributes)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


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

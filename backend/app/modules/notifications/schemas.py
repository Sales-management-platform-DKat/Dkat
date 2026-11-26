"""Response bodies of the notification API (camelCase JSON, snake_case attributes)."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer
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
    created_at: datetime  # database server time (CURRENT_TIMESTAMP), kept as stored

    @field_serializer("sent_at", "last_attempt_at")
    def _utc(self, value: datetime | None) -> str | None:
        """Stored naive in UTC by the notification service: say so, or browsers read them as local time."""
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat().replace("+00:00", "Z")


class PreorderNotificationsOut(CamelModel):
    preorder_id: int
    preorder_code: str
    max_auto_retries: int
    items: list[NotificationOut]  # oldest first


class ResendOut(CamelModel):
    result: Literal["SENT", "FAILED"]  # outcome of this re-send
    notification: NotificationOut

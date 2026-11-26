"""Notification history and manual re-send (FR-09.5). Mounted under /api/v1."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.mailer import mask_email
from app.core.permissions import Actor, require_auth, require_branch_access
from app.core.sms import mask_phone
from app.db.session import engine
from app.modules.notifications import repository
from app.modules.notifications.retry import resend_notification
from app.modules.notifications.schemas import NotificationOut, PreorderNotificationsOut, ResendOut

router = APIRouter(tags=["notifications"])
Reader = Annotated[Actor, Depends(require_auth)]
RecordId = Annotated[int, Path(gt=0, le=9223372036854775807)]


def to_out(row: dict) -> NotificationOut:
    recipient = mask_phone(row["recipient"]) if row["channel"] == "SMS" else mask_email(row["recipient"])
    return NotificationOut(
        id=row["notification_id"], preorder_id=row["preorder_id"], event_type=row["event_type"],
        channel=row["channel"], recipient=recipient, message=row["message"], status=row["status"],
        retry_count=row["retry_count"], can_resend=row["status"] == "FAILED",
        provider_message_id=row["provider_message_id"], error_message=row["error_message"],
        sent_at=row["sent_at"], last_attempt_at=row["last_attempt_at"], created_at=row["created_at"],
    )


def _check_branch(actor: Actor, branch_id: int, store_id: int, not_found_code: str) -> None:
    """Another store's record -> 404 (do not reveal it exists); another branch of the store -> 403."""
    if store_id != actor.store_id:
        raise HTTPException(404, {"code": not_found_code})
    try:
        with engine.connect() as db:
            require_branch_access(db, actor, branch_id)
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.get("/preorders/{preorder_id}/notifications")
async def preorder_notifications(preorder_id: RecordId, actor: Reader) -> PreorderNotificationsOut:
    """Lịch sử thông báo của đơn đặt trước: mỗi lần gửi 1 dòng (kênh, người nhận đã che, trạng thái, số lần gửi lại, lỗi)."""
    preorder = await repository.load_preorder(preorder_id)
    if preorder is None:
        raise HTTPException(404, {"code": "PREORDER_NOT_FOUND"})
    _check_branch(actor, preorder["branch_id"], preorder["store_id"], "PREORDER_NOT_FOUND")
    rows = await repository.list_for_preorder(preorder_id)
    return PreorderNotificationsOut(preorder_id=preorder_id, preorder_code=preorder["code"],
                                    max_auto_retries=settings.NOTIFY_MAX_RETRIES, items=[to_out(r) for r in rows])


@router.post("/notifications/{notification_id}/resend")
async def resend(notification_id: RecordId, actor: Reader) -> ResendOut:
    """Gửi lại ngay một thông báo FAILED (cùng kênh, người nhận, nội dung), tăng retryCount.
    200 + result SENT/FAILED; 409 NOTIFICATION_NOT_FAILED nếu đã SENT hoặc đang được gửi."""
    row = await repository.get_notification(notification_id)
    if row is None:
        raise HTTPException(404, {"code": "NOTIFICATION_NOT_FOUND"})
    _check_branch(actor, row["branch_id"], row["store_id"], "NOTIFICATION_NOT_FOUND")
    if row["status"] != "FAILED":
        raise HTTPException(409, {"code": "NOTIFICATION_NOT_FAILED",
                                  "message": f"Chỉ gửi lại được thông báo FAILED (hiện tại: {row['status']})"})
    outcome = await resend_notification(notification_id, automatic=False)
    if outcome["result"] == "NOT_FAILED":  # the job or another click took it first
        raise HTTPException(409, {"code": "NOTIFICATION_NOT_FAILED",
                                  "message": "Thông báo đang được gửi lại hoặc đã gửi thành công"})
    if outcome["notification"] is None:
        raise HTTPException(500, {"code": "INTERNAL_ERROR", "message": "Không gửi lại được thông báo"})
    return ResendOut(result=outcome["result"], notification=to_out(outcome["notification"]))

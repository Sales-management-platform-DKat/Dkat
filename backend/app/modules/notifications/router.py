"""Notification history and manual resend (FR-09.5). All staff, limited to their branches.

GET  /preorders/{id}/notifications   history of one pre-order (every attempt, oldest first)
POST /notifications/{id}/resend      re-send a FAILED notification now (staff button)
"""
from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.mailer import mask_email
from app.core.permissions import CurrentUser, ensure_branch_access, require_auth
from app.core.sms import mask_phone
from app.db.session import get_db
from app.modules.notifications import repository
from app.modules.notifications.retry import resend_notification
from app.modules.notifications.schemas import NotificationOut, PreorderNotificationsOut, ResendOut
from app.utils.response import SuccessResponse, ok

router = APIRouter(tags=["notifications"])


def to_out(row: dict) -> NotificationOut:
    recipient = mask_phone(row["recipient"]) if row["channel"] == "SMS" else mask_email(row["recipient"])
    return NotificationOut(
        id=row["notification_id"],
        preorder_id=row["preorder_id"],
        event_type=row["event_type"],
        channel=row["channel"],
        recipient=recipient,
        message=row["message"],
        status=row["status"],
        retry_count=row["retry_count"],
        can_resend=row["status"] == "FAILED",
        provider_message_id=row["provider_message_id"],
        error_message=row["error_message"],
        sent_at=row["sent_at"],
        last_attempt_at=row["last_attempt_at"],
        created_at=row["created_at"],
    )


@router.get(
    "/preorders/{preorder_id}/notifications",
    response_model=SuccessResponse[PreorderNotificationsOut],
    response_model_by_alias=True,
)
async def preorder_notifications(
    preorder_id: int = Path(gt=0), user: CurrentUser = Depends(require_auth), db: AsyncSession = Depends(get_db)
):
    """Lịch sử thông báo của đơn đặt trước: mỗi lần gửi 1 dòng (kênh, người nhận đã che, trạng thái, số lần gửi lại, lỗi)."""
    preorder = await repository.load_preorder(preorder_id)
    if preorder is None:
        raise AppError.not_found("Không tìm thấy đơn đặt trước")
    await ensure_branch_access(db, user, preorder["branch_id"])  # other branch -> 403
    rows = await repository.list_for_preorder(preorder_id)
    return ok(
        PreorderNotificationsOut(
            preorder_id=preorder_id,
            preorder_code=preorder["code"],
            max_auto_retries=settings.NOTIFY_MAX_RETRIES,
            items=[to_out(r) for r in rows],
        )
    )


@router.post(
    "/notifications/{notification_id}/resend",
    response_model=SuccessResponse[ResendOut],
    response_model_by_alias=True,
)
async def resend(
    request: Request,
    notification_id: int = Path(gt=0),
    user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Gửi lại ngay một thông báo FAILED (cùng kênh, người nhận, nội dung), tăng retryCount.
    200 + result SENT/FAILED; 409 NOTIFICATION_NOT_FAILED nếu đã SENT hoặc đang gửi."""
    row = await repository.get_notification(notification_id)
    if row is None:
        raise AppError.not_found("Không tìm thấy thông báo")
    await ensure_branch_access(db, user, row["branch_id"])
    if row["status"] != "FAILED":
        raise AppError(409, "NOTIFICATION_NOT_FAILED", f"Chỉ gửi lại được thông báo FAILED (hiện tại: {row['status']})")

    outcome = await resend_notification(notification_id, automatic=False)
    if outcome["result"] == "NOT_FAILED":  # someone else (job or another click) took it first
        raise AppError(409, "NOTIFICATION_NOT_FAILED", "Thông báo đang được gửi lại hoặc đã gửi thành công")
    if outcome["notification"] is None:
        raise AppError(500, "INTERNAL_ERROR", "Không gửi lại được thông báo")
    return ok(ResendOut(result=outcome["result"], notification=to_out(outcome["notification"])))

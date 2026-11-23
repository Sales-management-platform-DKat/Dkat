import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core.permissions import Actor, require_auth
from app.db.session import engine
from app.modules.preorders.schemas import PreorderDetail, PreorderFilters, PreorderRecordId, PreorderSummary
from app.modules.preorders.services.payment import confirm_preorder_payment
from app.modules.preorders.services.queries import get_preorder, list_preorders
from app.modules.sales.schemas import ConfirmPaymentInput

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/preorders", tags=["preorders"])
Reader = Annotated[Actor, Depends(require_auth)]


@router.get("")
def get_preorders(actor: Reader, filters: Annotated[PreorderFilters, Query()]) -> list[PreorderSummary]:
    try:
        with engine.connect() as db:
            return list_preorders(db, actor, filters)
    except SQLAlchemyError:
        logger.exception("Preorder list failed")
        raise HTTPException(503, "Database unavailable") from None


@router.get("/{preorder_id}")
def get_preorder_detail(preorder_id: PreorderRecordId, actor: Reader) -> PreorderDetail:
    try:
        with engine.connect() as db:
            return get_preorder(db, actor, preorder_id)
    except SQLAlchemyError:
        logger.exception("Preorder detail failed")
        raise HTTPException(503, "Database unavailable") from None


@router.post("/{preorder_id}/confirm-payment")
def confirm_payment(preorder_id: PreorderRecordId, data: ConfirmPaymentInput, actor: Reader) -> PreorderDetail:
    try:
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            return confirm_preorder_payment(db, actor, preorder_id, data)
    except SQLAlchemyError:
        logger.exception("Preorder payment failed")
        raise HTTPException(503, "Database unavailable") from None

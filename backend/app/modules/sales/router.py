import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core.permissions import Actor, require_auth, require_owner_or_manager
from app.db.session import engine
from app.modules.sales.schemas import (
    CancelOrderInput, ConfirmPaymentInput, PendingSalesOrder, RefundOrderInput, SalesId, SalesOrderDetail,
    SalesOrderFilters, SalesOrderInput, SalesOrderSummary,
)
from app.modules.sales.service import (
    cancel_sales_order, confirm_payment, create_sales_order, get_sales_order, list_sales_orders, refund_sales_order,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sales-orders", tags=["sales-orders"])
Reader = Annotated[Actor, Depends(require_auth)]
RefundActor = Annotated[Actor, Depends(require_owner_or_manager)]


@router.post("", status_code=201)
def create_order(order: SalesOrderInput, actor: Reader) -> PendingSalesOrder:
    try:
        with engine.begin() as db:
            return create_sales_order(db, actor, order)
    except SQLAlchemyError:
        logger.exception("Sales order creation failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.get("")
def list_orders(actor: Reader, filters: Annotated[SalesOrderFilters, Query()]) -> list[SalesOrderSummary]:
    try:
        with engine.connect() as db:
            return list_sales_orders(db, actor, filters)
    except SQLAlchemyError:
        logger.exception("Sales order list failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.get("/{order_id}")
def get_order(order_id: SalesId, actor: Reader) -> SalesOrderDetail:
    try:
        with engine.connect() as db:
            return get_sales_order(db, actor, order_id)
    except SQLAlchemyError:
        logger.exception("Sales order detail failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.post("/{order_id}/cancel")
def cancel_order(order_id: SalesId, data: CancelOrderInput, actor: Reader) -> SalesOrderDetail:
    try:
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            return cancel_sales_order(db, actor, order_id, data.reason)
    except SQLAlchemyError:
        logger.exception("Sales order cancellation failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.post("/{order_id}/confirm-payment")
def confirm_order_payment(order_id: SalesId, data: ConfirmPaymentInput, actor: Reader) -> SalesOrderDetail:
    try:
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            return confirm_payment(db, actor, order_id, data)
    except SQLAlchemyError:
        logger.exception("Sales order payment failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None


@router.post("/{order_id}/refund")
def refund_order(order_id: SalesId, data: RefundOrderInput, actor: RefundActor) -> SalesOrderDetail:
    try:
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            return refund_sales_order(db, actor, order_id, data.reason)
    except SQLAlchemyError:
        logger.exception("Sales order refund failed")
        raise HTTPException(503, "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau.") from None

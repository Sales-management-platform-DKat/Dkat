import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.permissions import Actor, require_auth
from app.db.session import engine
from app.modules.sales.schemas import PendingSalesOrder, SalesOrderInput
from app.modules.sales.service import create_sales_order

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sales-orders", tags=["sales-orders"])


@router.post("", status_code=201)
def create_order(order: SalesOrderInput, actor: Annotated[Actor, Depends(require_auth)]) -> PendingSalesOrder:
    try:
        with engine.begin() as db:
            return create_sales_order(db, actor, order)
    except SQLAlchemyError:
        logger.exception("Sales order creation failed")
        raise HTTPException(503, "Database unavailable") from None

import logging

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from app.core.db_errors import database_error
from starlette.concurrency import run_in_threadpool

from app.db.session import engine
from app.modules.preorders.errors import PreorderError
from app.modules.preorders.rate_limit import limit_preorder_requests
from app.modules.preorders.schemas import CreatedPreorder, PreorderErrorBody, PreorderInput
from app.modules.preorders.services.creation import create_preorder

logger = logging.getLogger(__name__)


class PreorderRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                await run_in_threadpool(limit_preorder_requests, request)
                return await handler(request)
            except RequestValidationError as error:
                # Keep customer data out of errors; return only field paths and reasons.
                details = [{"field": ".".join(str(part) for part in item["loc"] if part != "body"),
                            "reason": item["msg"]} for item in error.errors()]
                return JSONResponse(status_code=422, content={
                    "code": "INVALID_PREORDER", "message": "Đơn đặt trước không hợp lệ", "details": details,
                })
            except PreorderError as error:
                return JSONResponse(status_code=error.status, headers=error.headers, content={
                    "code": error.code, "message": error.message, "details": error.details,
                })
            except SQLAlchemyError as exc:
                # Customers see the same generic reply; the log says whether the schema is behind.
                database_error(exc, "Public preorder request failed", logger)
                return JSONResponse(status_code=503, content={
                    "code": "DATABASE_UNAVAILABLE", "message": "Dịch vụ tạm thời không khả dụng", "details": [],
                })

        return handle


router = APIRouter(prefix="/preorders", tags=["preorders-public"], route_class=PreorderRoute)


@router.post("", status_code=201, responses={
    status: {"model": PreorderErrorBody} for status in (404, 409, 422, 429, 503)
})
def submit_preorder(data: PreorderInput) -> CreatedPreorder:
    with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
        return create_preorder(db, data)

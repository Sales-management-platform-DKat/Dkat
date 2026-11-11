"""Standard response formats.

Success: {"success": true, "data": ...}
Error:   {"success": false, "error": {"code", "message", "details"}}
"""
from typing import Any, Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Use as response_model so Swagger shows the right format: response_model=SuccessResponse[ProductOut]."""

    success: bool = True
    data: T


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody


def ok(data: Any = None) -> dict[str, Any]:
    """Return from a route: `return ok(item)` (status code comes from the decorator)."""
    return {"success": True, "data": data}


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {"success": False, "error": {"code": code, "message": message, "details": details}}
        ),
    )

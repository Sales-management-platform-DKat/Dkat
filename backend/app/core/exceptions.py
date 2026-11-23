"""AppError and the centralized exception handlers -> always return standard JSON."""
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.utils.logger import get_logger
from app.utils.response import error_response

logger = get_logger("app.errors")


class AppError(Exception):
    """Expected business error. Raise it anywhere (service/repository/router)."""

    def __init__(
        self, status_code: int, code: str, message: str, details: Any = None, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers  # e.g. Retry-After on 429

    @classmethod
    def bad_request(cls, message: str = "Bad request", details: Any = None) -> "AppError":
        return cls(400, "BAD_REQUEST", message, details)

    @classmethod
    def unauthorized(cls, message: str = "Authentication required") -> "AppError":
        return cls(401, "UNAUTHORIZED", message)

    @classmethod
    def forbidden(cls, message: str = "Permission denied") -> "AppError":
        return cls(403, "FORBIDDEN", message)

    @classmethod
    def not_found(cls, message: str = "Resource not found", details: Any = None) -> "AppError":
        return cls(404, "NOT_FOUND", message, details)

    @classmethod
    def conflict(cls, message: str = "Conflict", details: Any = None) -> "AppError":
        return cls(409, "CONFLICT", message, details)

    @classmethod
    def validation(cls, message: str = "Validation failed", details: Any = None) -> "AppError":
        return cls(422, "VALIDATION_ERROR", message, details)


# Map HTTP status -> default error code (for HTTPException raised by FastAPI/Starlette)
_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
}


async def app_error_handler(request: Request, exc: AppError):
    response = error_response(exc.status_code, exc.code, exc.message, exc.details)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    if exc.status_code == 404 and exc.detail == "Not Found":
        message = f"Route {request.method} {request.url.path} not found"
    else:
        message = str(exc.detail)
    response = error_response(exc.status_code, code, message)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        if err.get("type") == "json_invalid":
            return error_response(400, "INVALID_JSON", "Request body is not valid JSON")
        details.append(
            {
                "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
                "message": err.get("msg"),
                "type": err.get("type"),
            }
        )
    return error_response(422, "VALIDATION_ERROR", "Invalid request data", details)


def _db_detail(exc: SQLAlchemyError) -> Any:
    return None if settings.is_production else str(getattr(exc, "orig", exc))


async def integrity_error_handler(request: Request, exc: IntegrityError):
    # 1062 = duplicate entry, 1451/1452 = foreign key
    errno = getattr(getattr(exc, "orig", None), "args", [None])[0]
    if errno == 1062:
        return error_response(409, "CONFLICT", "Duplicate entry", _db_detail(exc))
    if errno in (1451, 1452):
        return error_response(409, "CONFLICT", "Foreign key constraint failed", _db_detail(exc))
    return error_response(409, "CONFLICT", "Data integrity error", _db_detail(exc))


async def operational_error_handler(request: Request, exc: OperationalError):
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc.orig)
    return error_response(503, "DATABASE_UNAVAILABLE", "Database is unavailable", _db_detail(exc))


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    details = None if settings.is_production else {"type": type(exc).__name__, "message": str(exc)}
    return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Internal server error", details)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

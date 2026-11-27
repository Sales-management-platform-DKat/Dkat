"""Turns a database failure into the 503 the API returns.

A query against a column or table the database does not have (MySQL 1054 / 1146) is not
an outage: the schema is older than the code and a script in database/ was not applied.
Saying "cannot connect" sends whoever is on call in the wrong direction, so that case gets
its own code. The full error (SQL, column name) is only written to the server log.
"""
import logging

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("app.errors")

SCHEMA_ERROR_CODES = {1054, 1146}  # ER_BAD_FIELD_ERROR, ER_NO_SUCH_TABLE
DATABASE_UNAVAILABLE = "Không thể kết nối cơ sở dữ liệu. Vui lòng thử lại sau."
SCHEMA_OUTDATED = {
    "code": "DATABASE_SCHEMA_OUTDATED",
    "message": "Cơ sở dữ liệu chưa được cập nhật cho phiên bản này. Vui lòng báo quản trị viên chạy migration.",
}


def is_schema_error(exc: BaseException) -> bool:
    args = getattr(getattr(exc, "orig", None), "args", ())
    return bool(args) and args[0] in SCHEMA_ERROR_CODES


def database_error(exc: SQLAlchemyError, context: str = "Database operation failed",
                   log: logging.Logger | None = None) -> HTTPException:
    """Log `exc` (on the caller's logger when given) and return the HTTPException to raise:
    `raise database_error(exc, "Preorder list failed", logger) from None`."""
    log = log or logger
    if is_schema_error(exc):
        log.error("%s: database schema is outdated (%s). Run: python -m scripts.db_migrate", context, exc.orig)
        return HTTPException(503, SCHEMA_OUTDATED)
    log.exception("%s", context, exc_info=exc)
    return HTTPException(503, DATABASE_UNAVAILABLE)

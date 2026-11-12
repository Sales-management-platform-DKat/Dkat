from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


class CatalogNotFound(Exception):
    pass


class CatalogConflict(Exception):
    pass


class CatalogInvalid(Exception):
    pass


@contextmanager
def catalog_transaction(*, read_committed: bool = False):
    bind = engine
    if read_committed and engine.dialect.name == "mysql":
        bind = engine.execution_options(isolation_level="READ COMMITTED")
    try:
        with bind.begin() as db:
            yield db
    except CatalogNotFound as error:
        raise HTTPException(404, str(error)) from None
    except CatalogConflict as error:
        raise HTTPException(409, str(error)) from None
    except CatalogInvalid as error:
        raise HTTPException(422, str(error)) from None
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None

"""Base class for every SQLAlchemy model (app/modules/*/models.py)."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

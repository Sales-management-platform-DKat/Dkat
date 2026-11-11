from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import database_url

engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 5,
        "init_command": "SET SESSION time_zone = '+00:00'",
    },
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db

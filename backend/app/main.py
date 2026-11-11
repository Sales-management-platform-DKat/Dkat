"""Entry point. Run: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import close_engine, ping_database
from app.middlewares.request_logger import RequestLoggerMiddleware
from app.utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if await ping_database():
        logger.info("MySQL connected: %s@%s:%s/%s", settings.DB_USER, settings.DB_HOST, settings.DB_PORT, settings.DB_NAME)
    else:
        # The server stays up; /health reports database: "down"
        logger.warning("MySQL not reachable. Check DB_* in .env")
    yield
    await close_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Added last = outermost, so it logs every request including errors
    app.add_middleware(RequestLoggerMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=not settings.is_production)

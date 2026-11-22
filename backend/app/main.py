import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine
from app.core.config import CORS_ORIGINS
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.admin.router import router as admin_router
from app.modules.inventory.router import router as inventory_router
from app.modules.products.category_router import router as categories_router
from app.modules.products.router import router as products_router
from app.modules.sales.router import router as sales_router
from app.modules.preorders.public_router import router as public_preorders_router
from app.modules.preorders.router import router as preorders_router
from app.workers.preorder_expiry import run_preorder_expiry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    expiry_task = asyncio.create_task(run_preorder_expiry(stop))
    try:
        yield
    finally:
        stop.set()
        await expiry_task


app = FastAPI(title="DKat API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(products_router)
app.include_router(categories_router)
app.include_router(inventory_router)
app.include_router(sales_router)
app.include_router(public_preorders_router)
app.include_router(preorders_router)


@app.get("/health/db")
def database_health() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}

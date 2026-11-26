import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import CORS_ORIGINS, settings
from app.db.base import Base
from app.db.session import engine
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.branches.router import router as branches_router
from app.modules.catalog.router import router as catalog_router
from app.modules.auth.account import router as account_router
from app.modules.stores.router import router as stores_router
from app.modules.customers.router import router as customers_router
from app.modules.inventory.router import router as inventory_router
from app.modules.notifications.retry import run_retry_loop
from app.modules.notifications.router import router as notifications_router
from app.modules.products.category_router import router as categories_router
from app.modules.products.router import router as products_router
from app.modules.reports.router import router as reports_router
from app.modules.preorders.public_router import router as public_preorders_router
from app.modules.preorders.router import router as preorders_router
from app.modules.sales.router import router as sales_router
from app.modules.users.router import router as users_router
from app.workers.preorder_expiry import run_preorder_expiry


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # PBI 140: expire READY / NOTIFIED pre-orders past their hold deadline and hand the stock to the
    # next customers (FIFO). Lost in merge 9cc2512, restored for BUG-006.
    stop = asyncio.Event()
    expiry_task = asyncio.create_task(run_preorder_expiry(stop))
    # FR-09.5: re-send FAILED notifications every NOTIFY_RETRY_INTERVAL_SECONDS
    retry_task = asyncio.create_task(run_retry_loop()) if settings.NOTIFY_RETRY_ENABLED else None
    try:
        yield
    finally:
        stop.set()
        await expiry_task
        if retry_task is not None:
            retry_task.cancel()
            try:
                await retry_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="DKat API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
    allow_credentials=True,
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(branches_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(sales_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(public_preorders_router, prefix="/api/v1")
app.include_router(preorders_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")  # /public: no login, rate limited
app.include_router(account_router, prefix="/api/v1")  # /auth/me (PUT), password, sessions
app.include_router(stores_router, prefix="/api/v1")


@app.get("/health")
def health():
    try:
        with engine.connect() as db:
            db.execute(text("SELECT user_id FROM users LIMIT 0"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable_or_incompatible"},
        )
    return {"status": "ok", "database": "up"}



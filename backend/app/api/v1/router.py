"""Root router for /api/v1. Register each module's router here once it is written.

Example:
    from app.modules.products.router import router as products_router
    api_router.include_router(products_router)
"""
from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.branches.router import router as branches_router
from app.modules.catalog.router import router as catalog_router
from app.modules.customers.router import router as customers_router
from app.modules.health.router import router as health_router
from app.modules.inventory.router import router as inventory_router
from app.modules.products.router import router as products_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(branches_router)
api_router.include_router(users_router)
api_router.include_router(customers_router)
api_router.include_router(products_router)
api_router.include_router(inventory_router)
api_router.include_router(catalog_router)  # /public: no login, rate limited

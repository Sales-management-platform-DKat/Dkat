"""Root router for /api/v1. Register each module's router here once it is written.

Example:
    from app.modules.products.router import router as products_router
    api_router.include_router(products_router)
"""
from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.health.router import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)

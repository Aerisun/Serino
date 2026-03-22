from __future__ import annotations

from fastapi import APIRouter

from .admin import admin_router
from .public import router as public_router

api_router = APIRouter()
api_router.include_router(public_router)
api_router.include_router(admin_router)

from .search import router as search_router
api_router.include_router(search_router)

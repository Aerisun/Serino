from __future__ import annotations

from fastapi import APIRouter

from .admin import admin_router
from .mcp import router as mcp_router
from .site import router as site_router
from .site_auth_api import router as site_auth_router
from .site_interactions import router as site_interactions_router
from .site_search import router as site_search_router

api_router = APIRouter()
api_router.include_router(site_router)
api_router.include_router(site_auth_router)
api_router.include_router(site_interactions_router)
api_router.include_router(site_search_router)
api_router.include_router(mcp_router)
api_router.include_router(admin_router)

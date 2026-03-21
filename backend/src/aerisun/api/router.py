from __future__ import annotations

from fastapi import APIRouter

from .public import router as public_router

api_router = APIRouter()
api_router.include_router(public_router)


from __future__ import annotations

from fastapi import APIRouter

from aerisun.api.v1.public import router as public_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(public_router)


from __future__ import annotations

from fastapi import APIRouter

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry

from .assets import router as assets_router
from .auth import router as auth_router
from .content import build_crud_router
from .moderation import router as moderation_router
from .resume import router as resume_router
from .schemas import ContentAdminRead, ContentCreate, ContentUpdate
from .site_config import router as site_config_router
from .social import router as social_router
from .system import router as system_router

admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Auth
admin_router.include_router(auth_router)

# Content CRUD routers
for model, prefix in [
    (PostEntry, "/posts"),
    (DiaryEntry, "/diary"),
    (ThoughtEntry, "/thoughts"),
    (ExcerptEntry, "/excerpts"),
]:
    admin_router.include_router(
        build_crud_router(
            model,
            create_schema=ContentCreate,
            update_schema=ContentUpdate,
            read_schema=ContentAdminRead,
            prefix=prefix,
            tag=f"admin-{prefix.strip('/')}",
        )
    )

# Other admin routes
admin_router.include_router(site_config_router)
admin_router.include_router(resume_router)
admin_router.include_router(social_router)
admin_router.include_router(moderation_router)
admin_router.include_router(assets_router)
admin_router.include_router(system_router)

__all__ = ["admin_router"]

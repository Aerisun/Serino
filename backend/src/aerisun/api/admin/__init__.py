from __future__ import annotations

from fastapi import APIRouter, Depends


def _build_admin_router() -> APIRouter:
    from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
    from aerisun.domain.content.service import normalize_content_create_state, normalize_content_update_state

    from .assets import router as assets_router
    from .auth import router as auth_router
    from .automation import router as automation_router
    from .content import build_crud_router
    from .content_meta import router as content_meta_router
    from .deps import require_admin_console_access
    from .diary import router as diary_router
    from .import_export import router as import_export_router
    from .moderation import router as moderation_router
    from .object_storage import router as object_storage_router
    from .proxy_config import router as proxy_config_router
    from .resume import router as resume_router
    from .schemas import ContentAdminRead, ContentCreate, ContentUpdate
    from .site_config import router as site_config_router
    from .social import router as social_router
    from .subscriptions import router as subscriptions_router
    from .system import integrations_router
    from .system import router as system_router
    from .visitors import router as visitors_router

    admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
    protected_router = APIRouter(dependencies=[Depends(require_admin_console_access)])
    admin_router.include_router(auth_router)

    for model, prefix in [
        (PostEntry, "/posts"),
        (DiaryEntry, "/diary"),
        (ThoughtEntry, "/thoughts"),
        (ExcerptEntry, "/excerpts"),
    ]:
        content_type = prefix.strip("/")
        protected_router.include_router(
            build_crud_router(
                model,
                create_schema=ContentCreate,
                update_schema=ContentUpdate,
                read_schema=ContentAdminRead,
                prefix=prefix,
                tag=f"admin-{prefix.strip('/')}",
                prepare_create_data=lambda session, data, *, content_type=content_type: normalize_content_create_state(
                    session,
                    {**data, "_content_type": content_type},
                ),
                prepare_update_data=normalize_content_update_state,
            )
        )

    protected_router.include_router(diary_router)
    protected_router.include_router(site_config_router)
    protected_router.include_router(subscriptions_router)
    protected_router.include_router(proxy_config_router)
    protected_router.include_router(object_storage_router)
    protected_router.include_router(resume_router)
    protected_router.include_router(social_router)
    protected_router.include_router(moderation_router)
    protected_router.include_router(assets_router)
    protected_router.include_router(system_router)
    protected_router.include_router(integrations_router)
    protected_router.include_router(automation_router)
    protected_router.include_router(content_meta_router)
    protected_router.include_router(import_export_router)
    protected_router.include_router(visitors_router)
    admin_router.include_router(protected_router)
    return admin_router


__all__ = ["admin_router"]


def __getattr__(name: str):
    if name == "admin_router":
        return _build_admin_router()
    raise AttributeError(name)

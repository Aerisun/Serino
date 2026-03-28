"""Middleware registration — extracted from main.py."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from aerisun.api.admin.audit_middleware import AuditLogMiddleware
from aerisun.core.csrf import OriginCheckMiddleware
from aerisun.core.logging import RequestIDMiddleware
from aerisun.core.security_headers import SecurityHeadersMiddleware
from aerisun.core.settings import Settings
from aerisun.domain.site_config.service import _runtime_site_settings_read


def _resolve_allowed_origins(settings: Settings, session: Session | None = None) -> list[str]:
    if settings.environment == "development":
        return settings.cors_origins

    override = [item.strip() for item in (settings.production_cors_origins_override or []) if item.strip()]
    if override:
        return override

    if session is None:
        return settings.cors_origins
    try:
        runtime = _runtime_site_settings_read(session)
    except Exception:
        return settings.cors_origins
    return runtime.production_cors_origins or settings.cors_origins


def register_middleware(app: FastAPI, settings: Settings, session: Session | None = None) -> None:
    """Add all middleware layers to *app* in the correct order."""
    resolved_cors_origins = _resolve_allowed_origins(settings, session)
    dev_localhost = settings.environment == "development" and settings.has_only_localhost_origins()

    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(
        OriginCheckMiddleware,
        allowed_origins=resolved_cors_origins,
        allow_any_localhost=dev_localhost,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_cors_origins if not dev_localhost else [],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$" if dev_localhost else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

"""Middleware registration — extracted from main.py."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aerisun.api.admin.audit_middleware import AuditLogMiddleware
from aerisun.core.csrf import OriginCheckMiddleware
from aerisun.core.logging import RequestIDMiddleware
from aerisun.core.security_headers import SecurityHeadersMiddleware
from aerisun.core.settings import Settings


def register_middleware(app: FastAPI, settings: Settings) -> None:
    """Add all middleware layers to *app* in the correct order."""
    allow_any_origin = settings.environment == "development"
    dev_localhost = allow_any_origin and settings.has_only_localhost_origins()

    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(
        OriginCheckMiddleware,
        allowed_origins=settings.cors_origins,
        allow_any_localhost=dev_localhost,
        allow_any_origin=allow_any_origin,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_any_origin else settings.cors_origins if not dev_localhost else [],
        allow_origin_regex=(
            None
            if allow_any_origin
            else r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
            if dev_localhost
            else None
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

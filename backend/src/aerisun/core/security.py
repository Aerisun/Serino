"""Startup security checks — extracted from main.py."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from aerisun.core.settings import Settings
from aerisun.domain.site_config.service import _runtime_site_settings_read

logger = logging.getLogger("aerisun.startup")


def check_insecure_defaults(settings: Settings, session: Session | None = None) -> None:
    """Warn or abort when insecure defaults are detected."""
    issues: list[str] = []

    waline_secret = settings.waline_jwt_secret()
    if not waline_secret.configured or waline_secret.matches_any("change-me", "dev-only-insecure-token"):
        issues.append(f"{waline_secret.key} ({waline_secret.filename})")

    has_only_localhost_origins = settings.has_only_localhost_origins()

    if settings.environment != "development":
        override = [item.strip() for item in (settings.production_cors_origins_override or []) if item.strip()]
        if override:
            has_only_localhost_origins = all(settings._LOCALHOST_RE.match(o) for o in override)
        elif session is not None:
            try:
                runtime = _runtime_site_settings_read(session)
                if runtime.production_cors_origins:
                    has_only_localhost_origins = False
            except Exception:
                pass

    if settings.environment != "development":
        try:
            runtime = _runtime_site_settings_read(session) if session is not None else None
            if runtime is not None and not runtime.public_site_url.strip():
                issues.append("public_site_url (missing)")
        except Exception:
            issues.append("public_site_url (missing)")

    if has_only_localhost_origins:
        issues.append("CORS origins (only localhost)")
    if not issues:
        return
    msg = f"SECURITY: insecure defaults detected: {', '.join(issues)}. Update them before deploying."
    if settings.environment == "development":
        return
    if settings.environment == "production":
        logger.critical(msg)
        raise SystemExit(msg)
    logger.warning(msg)

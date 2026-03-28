"""Startup security checks — extracted from main.py."""

from __future__ import annotations

import logging
import os

from aerisun.core.settings import Settings

logger = logging.getLogger("aerisun.startup")


def check_insecure_defaults(settings: Settings) -> None:
    """Warn or abort when insecure defaults are detected."""
    issues: list[str] = []
    if os.environ.get("WALINE_JWT_TOKEN", "change-me") == "change-me":
        issues.append("WALINE_JWT_TOKEN")
    if settings.has_only_localhost_origins():
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

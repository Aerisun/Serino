"""Sentry SDK initialisation — extracted from main.py."""

from __future__ import annotations

import logging

from aerisun.core.settings import Settings

logger = logging.getLogger("aerisun.startup")


def init_sentry(settings: Settings) -> None:
    """Conditionally initialise the Sentry SDK if a DSN is configured."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logger.info("Sentry initialised (env=%s)", settings.environment)

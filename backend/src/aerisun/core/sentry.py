"""Sentry SDK initialisation — extracted from main.py."""

from __future__ import annotations

import logging

from aerisun.core.settings import Settings

logger = logging.getLogger("aerisun.startup")


def init_sentry(settings: Settings) -> None:
    """Conditionally initialise the Sentry SDK if a DSN is configured."""
    secret = settings.sentry_dsn_secret()
    if not secret.value:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=secret.value,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logger.info("Sentry initialised (env=%s, source=%s)", settings.environment, secret.source)

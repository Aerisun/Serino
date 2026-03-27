"""Phased application lifecycle management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from aerisun.core.db import dispose_engine
from aerisun.core.logging import setup_logging
from aerisun.core.security import check_insecure_defaults
from aerisun.core.sentry import init_sentry
from aerisun.core.settings import get_settings
from aerisun.core.task_manager import TaskManager
from aerisun.domain.ops.service import start_visit_record_worker, stop_visit_record_worker

logger = logging.getLogger("aerisun.bootstrap")


@asynccontextmanager
async def lifespan(_app):
    """Three-phase startup, reverse-order shutdown."""
    settings = get_settings()

    # Phase 1: Infrastructure
    settings.ensure_directories()
    setup_logging(settings)
    logger.info("Infrastructure ready")

    # Phase 2: Integrations
    check_insecure_defaults(settings)
    init_sentry(settings)
    logger.info("Integrations ready")

    # Phase 3: Background services
    task_manager = TaskManager(settings)
    await task_manager.start()
    await start_visit_record_worker()
    logger.info("Background services started")

    try:
        yield
    finally:
        # Reverse-order shutdown
        logger.info("Shutting down background services")
        await stop_visit_record_worker()
        await task_manager.stop()
        logger.info("Disposing database engine")
        dispose_engine()
        logger.info("Shutdown complete")

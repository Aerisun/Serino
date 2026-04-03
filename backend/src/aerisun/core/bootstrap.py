"""Phased application lifecycle management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aerisun.core.db import dispose_engine
from aerisun.core.db_preflight import compute_seed_fingerprint, get_stored_seed_fingerprint, store_seed_metadata
from aerisun.core.logging import setup_logging
from aerisun.core.security import check_insecure_defaults
from aerisun.core.seed import seed_bootstrap_data
from aerisun.core.seed_profile import normalize_seed_profile, resolve_seed_path
from aerisun.core.sentry import init_sentry
from aerisun.core.settings import BACKEND_ROOT, get_settings
from aerisun.core.task_manager import TaskManager
from aerisun.domain.automation.runtime_registry import get_automation_runtime
from aerisun.domain.iam.service import repair_legacy_api_key_scopes
from aerisun.domain.ops.service import start_visit_record_worker, stop_visit_record_worker

logger = logging.getLogger("aerisun.bootstrap")


def _refresh_bootstrap_seed_on_reload_if_needed() -> None:
    settings = get_settings()
    if settings.environment != "development":
        return
    if normalize_seed_profile(settings.seed_profile) != "seed":
        return
    if settings.seed_dev_data:
        return

    seed_path = resolve_seed_path(Path(BACKEND_ROOT / "src" / "aerisun" / "core"), seed_profile=settings.seed_profile)
    current_fp = compute_seed_fingerprint(seed_path, seed_profile=settings.seed_profile)
    stored_fp = get_stored_seed_fingerprint(settings.db_path)

    if stored_fp == current_fp:
        return

    logger.info(
        "Detected production seed change during development reload; reseeding database"
        " (stored_fingerprint=%s, current_fingerprint=%s)",
        stored_fp,
        current_fp,
    )
    seed_bootstrap_data(force=stored_fp is not None)
    store_seed_metadata(settings.db_path, fingerprint=current_fp)


@asynccontextmanager
async def lifespan(_app):
    """Three-phase startup, reverse-order shutdown."""
    settings = get_settings()

    # Phase 1: Infrastructure
    settings.ensure_directories()
    setup_logging(settings)
    _refresh_bootstrap_seed_on_reload_if_needed()
    from aerisun.core.db import get_session_factory

    factory = get_session_factory()
    with factory() as session:
        repaired_api_keys = repair_legacy_api_key_scopes(session)
    if repaired_api_keys:
        logger.info("Repaired legacy API key scopes", repaired=repaired_api_keys)
    logger.info("Infrastructure ready")

    # Phase 2: Integrations
    check_insecure_defaults(settings)
    init_sentry(settings)
    logger.info("Integrations ready")

    # Phase 3: Background services
    task_manager = TaskManager(settings)
    runtime = get_automation_runtime()
    runtime.start()
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
        runtime.stop()
        logger.info("Disposing database engine")
        dispose_engine()
        logger.info("Shutdown complete")

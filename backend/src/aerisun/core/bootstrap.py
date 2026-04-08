"""Phased application lifecycle management."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from aerisun.core.backfills import run_pending_backfills
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


class BackgroundServices:
    def __init__(self, settings) -> None:
        self._settings = settings
        self._task_manager: TaskManager | None = None
        self._runtime = None
        self._visit_worker_started = False

    async def start(self) -> None:
        started_at = perf_counter()
        self._task_manager = TaskManager(self._settings)
        self._runtime = get_automation_runtime()
        self._runtime.start()
        await self._task_manager.start()
        await start_visit_record_worker()
        self._visit_worker_started = True
        logger.info("Background services started in %.2fms", (perf_counter() - started_at) * 1000)

    async def stop(self) -> None:
        if self._visit_worker_started:
            await stop_visit_record_worker()
            self._visit_worker_started = False
        if self._task_manager is not None:
            await self._task_manager.stop()
            self._task_manager = None
        if self._runtime is not None:
            self._runtime.stop()
            self._runtime = None


def _log_background_start_result(task: asyncio.Task[None]) -> None:
    with contextlib.suppress(asyncio.CancelledError):
        exc = task.exception()
        if exc is not None:
            logger.exception("Background service startup failed", exc_info=exc)


@asynccontextmanager
async def lifespan(_app):
    """Minimal readiness startup, deferred background services, reverse-order shutdown."""
    settings = get_settings()
    infra_started_at = perf_counter()
    background_services = BackgroundServices(settings)
    background_task: asyncio.Task[None] | None = None

    settings.ensure_directories()
    setup_logging(settings)
    _refresh_bootstrap_seed_on_reload_if_needed()
    if settings.data_backfill_enabled:
        run_pending_backfills()
    check_insecure_defaults(settings)
    init_sentry(settings)
    logger.info("Application infrastructure ready in %.2fms", (perf_counter() - infra_started_at) * 1000)

    background_task = asyncio.create_task(background_services.start(), name="aerisun-background-start")
    background_task.add_done_callback(_log_background_start_result)

    try:
        yield
    finally:
        logger.info("Shutting down background services")
        if background_task is not None and not background_task.done():
            background_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await background_task
        elif background_task is not None:
            with contextlib.suppress(Exception):
                await background_task
        await background_services.stop()
        logger.info("Disposing database engine")
        dispose_engine()
        logger.info("Shutdown complete")

"""Background task orchestration — extracted from main.py."""

from __future__ import annotations

import asyncio
import logging

from aerisun.core.settings import Settings
from aerisun.core.tasks import cleanup_expired_sessions
from aerisun.domain.automation.runtime_registry import get_automation_runtime
from aerisun.domain.automation.service import dispatch_due_webhooks, execute_due_runs
from aerisun.domain.media.object_storage import (
    dispatch_due_asset_mirror_jobs,
    dispatch_due_remote_asset_delete_jobs,
    dispatch_due_remote_asset_upload_jobs,
    reconcile_object_storage_remote_sync,
)
from aerisun.domain.ops.backup_sync import dispatch_backup_sync
from aerisun.domain.ops.service import record_daily_traffic_snapshot

logger = logging.getLogger("aerisun.startup")


class TaskManager:
    """Lifecycle-aware manager for background tasks and schedulers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._async_tasks: list[asyncio.Task] = []
        self._scheduler = None  # type: ignore[assignment]

    async def start(self) -> None:
        self._async_tasks.append(asyncio.create_task(cleanup_expired_sessions()))

        from apscheduler.schedulers.background import BackgroundScheduler

        from aerisun.core.db import get_session_factory

        with get_session_factory()() as session:
            record_daily_traffic_snapshot(session)

        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._snapshot_daily_traffic,
            trigger="cron",
            hour=0,
            minute=5,
            id="traffic_daily_snapshot",
            name="Traffic daily snapshot",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        if self._settings.feed_crawl_enabled:
            from aerisun.domain.social.monitor import dispatch_due_social_checks

            self._scheduler.add_job(
                dispatch_due_social_checks,
                trigger="interval",
                minutes=1,
                id="friend_health_dispatcher",
                name="Friend health dispatcher",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

        self._scheduler.add_job(
            self._dispatch_workflow_runs,
            trigger="interval",
            seconds=15,
            id="workflow_run_dispatcher",
            name="Workflow run dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self._dispatch_webhooks,
            trigger="interval",
            seconds=15,
            id="webhook_delivery_dispatcher",
            name="Webhook delivery dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self._dispatch_backup_sync,
            trigger="interval",
            seconds=60,
            id="backup_sync_dispatcher",
            name="Backup sync dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self._dispatch_asset_mirror_jobs,
            trigger="interval",
            seconds=15,
            id="asset_mirror_dispatcher",
            name="Asset mirror dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self._dispatch_asset_remote_delete_jobs,
            trigger="interval",
            seconds=30,
            id="asset_remote_delete_dispatcher",
            name="Asset remote delete dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self._dispatch_asset_remote_upload_jobs,
            trigger="interval",
            seconds=20,
            id="asset_remote_upload_dispatcher",
            name="Asset remote upload dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self._reconcile_object_storage_remote_sync,
            trigger="interval",
            seconds=60,
            id="asset_remote_sync_reconcile_dispatcher",
            name="Asset remote sync reconcile dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        logger.info("Background scheduler started")

    def _snapshot_daily_traffic(self) -> None:
        from aerisun.core.db import get_session_factory

        with get_session_factory()() as session:
            record_daily_traffic_snapshot(session)

    def _dispatch_workflow_runs(self) -> None:
        from aerisun.core.db import get_session_factory

        runtime = get_automation_runtime()
        with get_session_factory()() as session:
            execute_due_runs(session, runtime)

    def _dispatch_webhooks(self) -> None:
        from aerisun.core.db import get_session_factory

        with get_session_factory()() as session:
            dispatch_due_webhooks(session)

    def _dispatch_backup_sync(self) -> None:
        dispatch_backup_sync()

    def _dispatch_asset_mirror_jobs(self) -> None:
        dispatch_due_asset_mirror_jobs()

    def _dispatch_asset_remote_delete_jobs(self) -> None:
        dispatch_due_remote_asset_delete_jobs()

    def _dispatch_asset_remote_upload_jobs(self) -> None:
        dispatch_due_remote_asset_upload_jobs()

    def _reconcile_object_storage_remote_sync(self) -> None:
        reconcile_object_storage_remote_sync()

    async def stop(self) -> None:
        for task in self._async_tasks:
            task.cancel()
        if self._async_tasks:
            await asyncio.gather(*self._async_tasks, return_exceptions=True)
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=True)

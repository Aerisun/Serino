"""Background task orchestration — extracted from main.py."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from aerisun.core.settings import Settings
from aerisun.core.tasks import cleanup_expired_sessions
from aerisun.core.time import shanghai_now
from aerisun.domain.automation import repository as automation_repository
from aerisun.domain.automation.runtime_registry import get_automation_runtime
from aerisun.domain.automation.service import dispatch_due_webhooks, execute_due_runs
from aerisun.domain.media.object_storage import (
    dispatch_due_asset_mirror_jobs,
    dispatch_due_local_asset_delete_jobs,
    dispatch_due_remote_asset_delete_jobs,
    dispatch_due_remote_asset_upload_jobs,
    reconcile_object_storage_remote_sync,
)
from aerisun.domain.ops.backup_sync import dispatch_backup_sync
from aerisun.domain.ops.diagnostics import (
    run_scheduled_system_diagnostics,
    run_system_diagnostics_if_stale,
)
from aerisun.domain.ops.service import record_daily_traffic_snapshot

logger = logging.getLogger("aerisun.startup")


class TaskManager:
    """Lifecycle-aware manager for background tasks and schedulers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._async_tasks: list[asyncio.Task] = []
        self._scheduler = None  # type: ignore[assignment]
        self._workflow_worker_id = f"task-manager:{socket.gethostname()}:{os.getpid()}:{uuid4().hex}"

    async def start(self) -> None:
        self._async_tasks.append(asyncio.create_task(cleanup_expired_sessions()))

        from apscheduler.schedulers.background import BackgroundScheduler

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
        self._scheduler.add_job(
            self._run_daily_system_diagnostics,
            trigger="cron",
            hour=4,
            minute=20,
            timezone=ZoneInfo("Asia/Shanghai"),
            id="system_diagnostics_daily",
            name="Daily system diagnostics",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=6 * 60 * 60,
        )
        self._scheduler.add_job(
            self._run_startup_system_diagnostics,
            trigger="date",
            run_date=shanghai_now() + timedelta(seconds=60),
            id="system_diagnostics_startup_catchup",
            name="Startup system diagnostics catch-up",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=5 * 60,
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
            self._dispatch_content_subscription_notifications,
            trigger="interval",
            seconds=30,
            id="content_subscription_notification_dispatcher",
            name="Content subscription notification dispatcher",
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
            self._dispatch_asset_local_delete_jobs,
            trigger="interval",
            seconds=15,
            id="asset_local_delete_dispatcher",
            name="Asset local delete dispatcher",
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

    def _run_daily_system_diagnostics(self) -> None:
        run_scheduled_system_diagnostics()

    def _run_startup_system_diagnostics(self) -> None:
        run_system_diagnostics_if_stale()

    def _dispatch_workflow_runs(self) -> None:
        from aerisun.core.db import get_session_factory

        runtime = get_automation_runtime()
        with get_session_factory()() as session:
            automation_repository.recover_expired_agent_runs(session, now=shanghai_now())
            session.commit()
            execute_due_runs(
                session,
                runtime,
                worker_id=self._workflow_worker_id,
                recover_expired=False,
            )

    def _dispatch_webhooks(self) -> None:
        from aerisun.core.db import get_session_factory

        with get_session_factory()() as session:
            dispatch_due_webhooks(session)

    def _dispatch_content_subscription_notifications(self) -> None:
        from aerisun.domain.subscription.service import dispatch_content_subscription_notifications

        dispatch_content_subscription_notifications()

    def _dispatch_backup_sync(self) -> None:
        dispatch_backup_sync()

    def _dispatch_asset_mirror_jobs(self) -> None:
        dispatch_due_asset_mirror_jobs()

    def _dispatch_asset_remote_delete_jobs(self) -> None:
        dispatch_due_remote_asset_delete_jobs()

    def _dispatch_asset_local_delete_jobs(self) -> None:
        dispatch_due_local_asset_delete_jobs()

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
        from aerisun.domain.automation.codex_app_server import close_codex_app_server_client

        close_codex_app_server_client()

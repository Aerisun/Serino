"""Background task orchestration — extracted from main.py."""

from __future__ import annotations

import asyncio
import logging

from aerisun.core.settings import Settings
from aerisun.core.tasks import cleanup_expired_sessions

logger = logging.getLogger("aerisun.startup")


class TaskManager:
    """Lifecycle-aware manager for background tasks and schedulers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._async_tasks: list[asyncio.Task] = []
        self._scheduler = None  # type: ignore[assignment]

    async def start(self) -> None:
        self._async_tasks.append(asyncio.create_task(cleanup_expired_sessions()))

        if self._settings.feed_crawl_enabled:
            from apscheduler.schedulers.background import BackgroundScheduler

            from aerisun.domain.social.crawler import crawl_all_feeds

            self._scheduler = BackgroundScheduler(daemon=True)
            self._scheduler.add_job(
                crawl_all_feeds,
                trigger="interval",
                hours=self._settings.feed_crawl_interval_hours,
                id="feed_crawler",
                name="Friend feed crawler",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            self._scheduler.start()
            logger.info("Feed crawler scheduler started (interval=%dh)", self._settings.feed_crawl_interval_hours)

    async def stop(self) -> None:
        for task in self._async_tasks:
            task.cancel()
        if self._async_tasks:
            await asyncio.gather(*self._async_tasks, return_exceptions=True)
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=True)

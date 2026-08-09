from __future__ import annotations

from datetime import datetime

import pytest

from aerisun.core.settings import Settings
from aerisun.core.task_manager import TaskManager


@pytest.mark.anyio
async def test_task_manager_registers_one_daily_diagnostic_and_one_startup_catchup(monkeypatch) -> None:
    jobs: list[dict[str, object]] = []

    class FakeScheduler:
        def __init__(self, *, daemon: bool) -> None:
            self.daemon = daemon

        def add_job(self, func, *, trigger, **kwargs) -> None:
            jobs.append({"func": func, "trigger": trigger, **kwargs})

        def start(self) -> None:
            return None

        def shutdown(self, *, wait: bool) -> None:
            return None

    async def no_cleanup() -> None:
        return None

    monkeypatch.setattr("apscheduler.schedulers.background.BackgroundScheduler", FakeScheduler)
    monkeypatch.setattr("aerisun.core.task_manager.cleanup_expired_sessions", no_cleanup)

    manager = TaskManager(Settings(environment="test", feed_crawl_enabled=False))
    await manager.start()
    await manager.stop()

    by_id = {str(job["id"]): job for job in jobs}
    daily = by_id["system_diagnostics_daily"]
    assert daily["trigger"] == "cron"
    assert daily["hour"] == 4
    assert daily["minute"] == 20
    assert str(daily["timezone"]) == "Asia/Shanghai"
    assert daily["max_instances"] == 1
    assert daily["coalesce"] is True
    assert daily["misfire_grace_time"] == 6 * 60 * 60

    startup = by_id["system_diagnostics_startup_catchup"]
    assert startup["trigger"] == "date"
    assert isinstance(startup["run_date"], datetime)
    assert 45 <= (startup["run_date"] - datetime.now(startup["run_date"].tzinfo)).total_seconds() <= 75

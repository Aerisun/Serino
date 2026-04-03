from __future__ import annotations

from pathlib import Path

import pytest


def configure_runtime_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    async def _inline_run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _inline_run_sync(func, *args, **kwargs):
        kwargs.pop("abandon_on_cancel", None)
        kwargs.pop("cancellable", None)
        kwargs.pop("limiter", None)
        if kwargs:
            return func(*args, **kwargs)
        return func(*args)

    import anyio.to_thread
    import fastapi.concurrency
    import fastapi.routing
    import starlette.concurrency
    import starlette.routing

    store_dir = tmp_path / "store"
    runtime_paths = {
        "store_dir": store_dir,
        "data_dir": store_dir,
        "media_dir": store_dir / "media",
        "secrets_dir": store_dir / "secrets",
        "db_path": store_dir / "aerisun.db",
        "waline_db_path": store_dir / "waline.db",
    }

    monkeypatch.setenv("AERISUN_STORE_DIR", str(runtime_paths["store_dir"]))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(runtime_paths["data_dir"]))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(runtime_paths["media_dir"]))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(runtime_paths["secrets_dir"]))
    monkeypatch.setenv("AERISUN_DB_PATH", str(runtime_paths["db_path"]))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(runtime_paths["waline_db_path"]))
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "test")
    monkeypatch.setenv("AERISUN_FEED_CRAWL_ENABLED", "false")
    monkeypatch.setenv("AERISUN_IP_GEO_ENABLED", "false")
    monkeypatch.setenv("AERISUN_SEED_DEV_DATA", "true")
    monkeypatch.setattr(anyio.to_thread, "run_sync", _inline_run_sync)
    monkeypatch.setattr(starlette.concurrency, "run_in_threadpool", _inline_run_in_threadpool)
    monkeypatch.setattr(starlette.routing, "run_in_threadpool", _inline_run_in_threadpool)
    monkeypatch.setattr(fastapi.concurrency, "run_in_threadpool", _inline_run_in_threadpool)
    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", _inline_run_in_threadpool)
    return runtime_paths


def reset_runtime_state() -> None:
    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.rate_limit import limiter
    from aerisun.core.settings import get_settings
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    limiter.enabled = False
    runtime = get_automation_runtime()
    runtime.stop()
    get_automation_runtime.cache_clear()
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def seed_runtime_data() -> None:
    from aerisun.core.dev_seed import seed_reference_data
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    seed_reference_data()
    get_automation_runtime().start()


def teardown_runtime_state() -> None:
    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.settings import get_settings
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    runtime = get_automation_runtime()
    runtime.stop()
    get_automation_runtime.cache_clear()
    engine = get_engine()
    engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()

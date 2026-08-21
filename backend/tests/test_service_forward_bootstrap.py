from __future__ import annotations

import asyncio

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_lifespan_rebuilds_service_forward_dispatcher_before_ready(monkeypatch) -> None:
    from aerisun.core import bootstrap

    events: list[str] = []

    class FakeSettings:
        def ensure_directories(self) -> None:
            events.append("ensure-directories")

    class FakeBackgroundServices:
        def __init__(self, _settings) -> None:
            pass

        async def start(self) -> None:
            events.append("background-start")

        async def stop(self) -> None:
            events.append("background-stop")

    settings = FakeSettings()
    monkeypatch.setattr(bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(bootstrap, "BackgroundServices", FakeBackgroundServices)
    monkeypatch.setattr(bootstrap, "ensure_route_dispatcher", lambda _settings: events.append("dispatcher"))
    monkeypatch.setattr(bootstrap, "setup_logging", lambda _settings: None)
    monkeypatch.setattr(bootstrap, "_refresh_bootstrap_seed_on_reload_if_needed", lambda: None)
    monkeypatch.setattr(bootstrap, "check_insecure_defaults", lambda _settings: None)
    monkeypatch.setattr(bootstrap, "init_sentry", lambda _settings: None)
    monkeypatch.setattr(bootstrap, "dispose_engine", lambda: None)

    async with bootstrap.lifespan(None):
        await asyncio.sleep(0)

    assert events[:3] == ["ensure-directories", "dispatcher", "background-start"]
    assert events[-1] == "background-stop"

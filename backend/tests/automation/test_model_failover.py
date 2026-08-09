from __future__ import annotations

from typing import Any

import pytest

from aerisun.domain.automation import runtime
from aerisun.domain.automation.codex_app_server import CodexAppServerUnavailable
from aerisun.domain.exceptions import ValidationError


def _router_config(*, primary: str = "chatgpt_oauth") -> dict[str, Any]:
    return {
        "schema_version": 2,
        "primary_source": primary,
        "chatgpt_oauth": {
            "enabled": True,
            "model": "gpt-5.2-codex",
            "timeout_seconds": 30,
        },
        "openai_compatible": {
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://api.example.test/v1",
            "model": "fallback-model",
            "api_key": "secret",
            "temperature": 0.2,
            "timeout_seconds": 20,
        },
    }


def _turn(payload: dict[str, Any]) -> runtime._ModelTurnResult:
    return {
        "raw_content": "{}",
        "parsed_content": payload,
        "tool_calls": [],
        "assistant_message": {"role": "assistant", "content": "{}"},
    }


def test_model_router_falls_back_and_opens_a_short_circuit(monkeypatch) -> None:
    calls: list[str] = []

    def fail_chatgpt(*args, **kwargs):
        calls.append("chatgpt_oauth")
        raise CodexAppServerUnavailable("offline")

    def pass_api(*args, **kwargs):
        calls.append("openai_compatible")
        return _turn({"route": "fallback"})

    runtime.reset_model_source_health()
    monkeypatch.setattr(runtime, "_invoke_chatgpt_turn", fail_chatgpt)
    monkeypatch.setattr(runtime, "_invoke_openai_compatible_turn", pass_api)

    assert runtime.invoke_model_json(_router_config(), messages=[]) == {"route": "fallback"}
    assert calls == ["chatgpt_oauth", "openai_compatible"]
    health = runtime.get_model_source_health()
    assert health["chatgpt_oauth"]["failure_count"] == 1
    assert health["chatgpt_oauth"]["cooldown_remaining_seconds"] > 0

    calls.clear()
    assert runtime.invoke_model_json(_router_config(), messages=[]) == {"route": "fallback"}
    assert calls == ["openai_compatible"]


def test_model_router_uses_only_the_primary_when_it_is_healthy(monkeypatch) -> None:
    calls: list[str] = []

    def pass_chatgpt(*args, **kwargs):
        calls.append("chatgpt_oauth")
        return _turn({"route": "primary"})

    def unexpected_api(*args, **kwargs):
        calls.append("openai_compatible")
        raise AssertionError("fallback should not be called")

    runtime.reset_model_source_health()
    monkeypatch.setattr(runtime, "_invoke_chatgpt_turn", pass_chatgpt)
    monkeypatch.setattr(runtime, "_invoke_openai_compatible_turn", unexpected_api)

    assert runtime.invoke_model_json(_router_config(), messages=[]) == {"route": "primary"}
    assert calls == ["chatgpt_oauth"]


def test_model_router_reports_failure_only_after_both_sources_fail(monkeypatch) -> None:
    runtime.reset_model_source_health()
    monkeypatch.setattr(
        runtime,
        "_invoke_chatgpt_turn",
        lambda *args, **kwargs: (_ for _ in ()).throw(CodexAppServerUnavailable("oauth unavailable")),
    )
    monkeypatch.setattr(
        runtime,
        "_invoke_openai_compatible_turn",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValidationError("api unavailable")),
    )

    with pytest.raises(ValidationError, match=r"ChatGPT OAuth.*OpenAI-compatible API"):
        runtime.invoke_model_json(_router_config(), messages=[])

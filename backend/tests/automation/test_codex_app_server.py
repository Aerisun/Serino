from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from aerisun.domain.automation.codex_app_server import (
    CodexAppServerClient,
    CodexAppServerTimeout,
    CodexAppServerUnavailable,
)


def _write_fake_codex(path: Path) -> Path:
    executable = path / "fake-codex"
    executable.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys

            logged_in = False
            trace_path = os.environ.get("FAKE_CODEX_TRACE", "")
            hang_method = os.environ.get("FAKE_CODEX_HANG_METHOD", "")
            fail_login_before_response = os.environ.get("FAKE_CODEX_FAIL_LOGIN_BEFORE_RESPONSE") == "1"

            def emit(payload):
                sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\\n")
                sys.stdout.flush()

            def trace(payload):
                if not trace_path:
                    return
                with open(trace_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, separators=(",", ":")) + "\\n")

            for line in sys.stdin:
                request = json.loads(line)
                trace({
                    **request,
                    "_proxy_environment": {
                        key: os.environ.get(key)
                        for key in (
                            "HTTP_PROXY",
                            "HTTPS_PROXY",
                            "ALL_PROXY",
                            "http_proxy",
                            "https_proxy",
                            "all_proxy",
                        )
                    },
                })
                request_id = request.get("id")
                method = request.get("method")
                params = request.get("params") or {}
                if method == hang_method:
                    continue
                if method == "initialize":
                    emit({"id": request_id, "result": {"userAgent": "fake", "codexHome": os.environ["CODEX_HOME"]}})
                elif method == "account/login/start":
                    if fail_login_before_response:
                        emit({
                            "method": "account/login/completed",
                            "params": {"loginId": "login-1", "success": False, "error": "denied"},
                        })
                    else:
                        logged_in = True
                    emit({
                        "id": request_id,
                        "result": {
                            "type": "chatgptDeviceCode",
                            "loginId": "login-1",
                            "verificationUrl": "https://auth.openai.com/device",
                            "userCode": "ABCD-EFGH",
                        },
                    })
                    if not fail_login_before_response:
                        emit({
                            "method": "account/login/completed",
                            "params": {"loginId": "login-1", "success": True, "error": None},
                        })
                elif method == "account/read":
                    account = (
                        {"type": "chatgpt", "email": "owner@example.com", "planType": "plus"}
                        if logged_in
                        else None
                    )
                    emit({"id": request_id, "result": {"account": account, "requiresOpenaiAuth": True}})
                elif method == "account/logout":
                    logged_in = False
                    emit({"id": request_id, "result": {}})
                elif method == "model/list":
                    emit({
                        "id": request_id,
                        "result": {
                            "data": [
                                {
                                    "id": "gpt-5.2-codex",
                                    "model": "gpt-5.2-codex",
                                    "displayName": "GPT-5.2 Codex",
                                    "description": "",
                                    "hidden": False,
                                    "isDefault": True,
                                    "defaultReasoningEffort": "medium",
                                    "supportedReasoningEfforts": [],
                                }
                            ],
                            "nextCursor": None,
                        },
                    })
                elif method == "thread/start":
                    emit({"id": request_id, "result": {"thread": {"id": "thread-1"}}})
                elif method == "turn/start":
                    emit({"id": request_id, "result": {"turn": {"id": "turn-1", "status": "inProgress", "items": []}}})
                    item = {
                        "id": "message-1",
                        "type": "agentMessage",
                        "phase": "final_answer",
                        "text": '{"decision":"approve"}',
                    }
                    emit({
                        "method": "item/completed",
                        "params": {
                            "threadId": "thread-1",
                            "turnId": "turn-1",
                            "completedAtMs": 1,
                            "item": item,
                        },
                    })
                    emit({
                        "method": "turn/completed",
                        "params": {
                            "threadId": "thread-1",
                            "turn": {"id": "turn-1", "status": "completed", "items": [item], "error": None},
                        },
                    })
                elif method == "thread/delete":
                    emit({"id": request_id, "result": {}})
                else:
                    emit({"id": request_id, "error": {"code": -32601, "message": "unsupported"}})
            """
        ),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _read_trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_codex_app_server_manages_device_login_models_and_structured_turn(tmp_path, monkeypatch) -> None:
    executable = _write_fake_codex(tmp_path)
    trace_path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("FAKE_CODEX_TRACE", str(trace_path))
    client = CodexAppServerClient(
        executable=str(executable),
        codex_home=tmp_path / "codex-home",
        workspace=tmp_path / "workspace",
        request_timeout_seconds=1,
        idle_timeout_seconds=60,
    )

    try:
        assert client.read_account() is None

        login = client.start_device_login()
        assert login.login_id == "login-1"
        assert login.verification_url == "https://auth.openai.com/device"
        assert login.user_code == "ABCD-EFGH"

        login_status = client.get_login_status(login.login_id)
        assert login_status.status == "completed"
        assert login_status.account is not None
        assert login_status.account.email == "owner@example.com"
        assert login_status.account.plan_type == "plus"

        models = client.list_models()
        assert [(item.model, item.is_default) for item in models] == [("gpt-5.2-codex", True)]

        result = client.run_json(
            model="gpt-5.2-codex",
            messages=[{"role": "user", "content": "Return the moderation decision."}],
            output_schema={
                "type": "object",
                "properties": {"decision": {"type": "string"}},
                "required": ["decision"],
                "additionalProperties": False,
            },
            timeout_seconds=2,
        )
        assert result == {"decision": "approve"}
        assert client.is_running is True
    finally:
        client.close()

    trace = _read_trace(trace_path)
    initialize = next(item for item in trace if item["method"] == "initialize")
    assert initialize["params"]["capabilities"]["experimentalApi"] is False

    thread_start = next(item for item in trace if item["method"] == "thread/start")
    assert (
        thread_start["params"]
        | {
            "sandbox": "read-only",
            "approvalPolicy": "never",
            "ephemeral": True,
        }
        == thread_start["params"]
    )

    turn_start = next(item for item in trace if item["method"] == "turn/start")
    assert turn_start["params"]["outputSchema"]["additionalProperties"] is False
    assert any(item["method"] == "thread/delete" for item in trace)
    assert (tmp_path / "codex-home").stat().st_mode & 0o077 == 0


def test_codex_app_server_stops_a_stuck_process_after_timeout(tmp_path, monkeypatch) -> None:
    executable = _write_fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_HANG_METHOD", "account/read")
    client = CodexAppServerClient(
        executable=str(executable),
        codex_home=tmp_path / "codex-home",
        workspace=tmp_path / "workspace",
        request_timeout_seconds=0.1,
        idle_timeout_seconds=60,
    )

    with pytest.raises(CodexAppServerTimeout):
        client.read_account()

    assert client.is_running is False


def test_codex_app_server_keeps_login_completion_received_before_start_response(tmp_path, monkeypatch) -> None:
    executable = _write_fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_FAIL_LOGIN_BEFORE_RESPONSE", "1")
    client = CodexAppServerClient(
        executable=str(executable),
        codex_home=tmp_path / "codex-home",
        workspace=tmp_path / "workspace",
        request_timeout_seconds=1,
        idle_timeout_seconds=60,
    )

    try:
        login = client.start_device_login()
        status = client.get_login_status(login.login_id)
    finally:
        client.close()

    assert status.status == "failed"
    assert status.error == "denied"


def test_codex_app_server_uses_only_the_configured_proxy_environment(tmp_path, monkeypatch) -> None:
    executable = _write_fake_codex(tmp_path)
    trace_path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("FAKE_CODEX_TRACE", str(trace_path))
    monkeypatch.setenv("HTTPS_PROXY", "http://inherited.invalid:9999")
    client = CodexAppServerClient(
        executable=str(executable),
        codex_home=tmp_path / "codex-home",
        workspace=tmp_path / "workspace",
        request_timeout_seconds=1,
        idle_timeout_seconds=60,
        proxy_url_provider=lambda: "http://proxy.internal:7890",
        require_proxy=True,
    )

    try:
        assert client.read_account() is None
    finally:
        client.close()

    initialize = next(item for item in _read_trace(trace_path) if item["method"] == "initialize")
    assert set(initialize["_proxy_environment"].values()) == {"http://proxy.internal:7890"}


def test_codex_app_server_refuses_to_start_without_the_required_proxy(tmp_path) -> None:
    client = CodexAppServerClient(
        executable=str(_write_fake_codex(tmp_path)),
        codex_home=tmp_path / "codex-home",
        workspace=tmp_path / "workspace",
        request_timeout_seconds=1,
        idle_timeout_seconds=60,
        proxy_url_provider=lambda: None,
        require_proxy=True,
    )

    with pytest.raises(CodexAppServerUnavailable, match="代理设置"):
        client.read_account()

    assert client.is_running is False

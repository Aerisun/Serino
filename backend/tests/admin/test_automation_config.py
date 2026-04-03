from __future__ import annotations

import json
import sqlite3
from typing import Any, ClassVar

import httpx

from aerisun.core.settings import get_settings
from aerisun.domain.agent.capabilities.registry import _json_schema_for_annotation
from aerisun.domain.automation import compat
from aerisun.domain.automation.ai_contract_context import build_ai_contract_context
from aerisun.domain.automation.catalog import build_workflow_catalog
from aerisun.domain.automation.events import emit_comment_pending, emit_guestbook_pending
from aerisun.domain.automation.packs import load_workflow_pack, workflow_pack_path, write_workflow_pack
from aerisun.domain.automation.runtime import (
    FINAL_OUTPUT_TOOL_NAME,
    AutomationRuntime,
    _ai_shell_input_payload,
    _effective_model_timeout_seconds,
    _enforce_tool_usage_policy,
)
from aerisun.domain.automation.schemas import (
    ActionSurfaceEntrySpec,
    ActionSurfaceSpec,
    AgentModelConfigUpdate,
    AgentWorkflowCreate,
    AgentWorkflowGraph,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowUpdate,
    ApprovalDecisionWrite,
    QuerySurfaceSpec,
    SurfaceBoundArgConfig,
    SurfaceRefBindingConfig,
    WebhookSubscriptionCreate,
)
from aerisun.domain.automation.service import (
    create_webhook_subscription,
    create_workflow_run,
    execute_due_runs,
    get_run_detail,
    list_pending_approvals,
    list_runs,
    list_webhook_deliveries,
    resolve_approval,
)
from aerisun.domain.automation.settings import (
    create_agent_workflow,
    delete_agent_workflow,
    get_agent_workflow,
    update_agent_model_config,
    update_agent_workflow,
)
from aerisun.domain.automation.tool_surface import (
    execute_action_surface,
    execute_tool_surface,
    list_action_surface_invocations,
)
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.site_config import repository as site_repo
from aerisun.domain.waline.service import connect_waline_db

ADMIN_BASE = "/api/v1/admin/automation"


def _seed_waiting_comment(
    connection: sqlite3.Connection,
    *,
    url: str,
    nick: str,
    comment: str,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO wl_comment (
            user_id, comment, insertedAt, ip, link, mail, nick, pid, rid,
            sticky, status, "like", ua, url, createdAt, updatedAt
        ) VALUES (
            NULL, ?, ?, '', NULL, NULL, ?, NULL, NULL,
            NULL, 'waiting', 0, '', ?, ?, ?
        )
        """,
        (
            comment,
            created_at,
            nick,
            url,
            created_at,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _set_ready_model_config(session) -> None:
    update_agent_model_config(
        session,
        AgentModelConfigUpdate(
            enabled=True,
            provider="openai_compatible",
            base_url="https://model.example/v1",
            model="probe-model",
            api_key="secret-key",
            temperature=0.1,
            timeout_seconds=12,
            advisory_prompt="Return strict JSON only.",
        ),
    )


def _mount_runtime_model_sequence(
    monkeypatch, responses: list[dict[str, Any] | str], captured_messages: list[list[dict[str, Any]]] | None = None
) -> list[dict[str, Any] | str]:
    remaining = list(responses)

    class FakeResponse:
        def __init__(self, body: dict[str, Any] | str) -> None:
            self._body = body

        def raise_for_status(self) -> None:
            return None

        def json(self):
            if isinstance(self._body, dict) and isinstance(self._body.get("__message__"), dict):
                message = dict(self._body["__message__"])
            else:
                content = self._body if isinstance(self._body, str) else json.dumps(self._body, ensure_ascii=False)
                message = {"content": content}
            return {"choices": [{"message": message}]}

    def fake_post(_url, *args, **kwargs):
        if not remaining:
            raise AssertionError("Model was called more times than the scripted sequence.")
        body = remaining.pop(0)
        if captured_messages is not None:
            payload = dict(kwargs.get("json") or {})
            captured_messages.append(list(payload.get("messages") or []))
        return FakeResponse(body)

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", fake_post)
    return remaining


def _final_output_tool_call(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_calls": [
            {
                "name": FINAL_OUTPUT_TOOL_NAME,
                "arguments": arguments,
            }
        ]
    }


def _native_tool_call_message(*calls: dict[str, Any], content: str = "") -> dict[str, Any]:
    return {
        "__message__": {
            "content": content,
            "tool_calls": [
                {
                    "id": str(call.get("id") or f"call_{index}"),
                    "type": "function",
                    "function": {
                        "name": str(call.get("name") or ""),
                        "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
                    },
                }
                for index, call in enumerate(calls, start=1)
            ],
        }
    }


def test_admin_agent_model_config_roundtrip(client, admin_headers) -> None:
    response = client.get(f"{ADMIN_BASE}/model-config", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["provider"] == "openai_compatible"
    assert response.json()["is_ready"] is False

    update_response = client.put(
        f"{ADMIN_BASE}/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key",
            "temperature": 0.3,
            "timeout_seconds": 15,
            "advisory_prompt": "Return strict JSON only.",
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["enabled"] is True
    assert payload["base_url"] == "https://api.openai.com/v1"
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["api_key"] == "secret-key"
    assert payload["temperature"] == 0.3
    assert payload["timeout_seconds"] == 15
    assert payload["is_ready"] is True

    reload_response = client.get(f"{ADMIN_BASE}/model-config", headers=admin_headers)
    assert reload_response.status_code == 200
    assert reload_response.json()["model"] == "gpt-4.1-mini"


def test_admin_agent_model_config_test_uses_payload(client, admin_headers, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"connection_ok","needs_approval":false,"proposed_action":"approve"}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *args, **kwargs):
        captured["url"] = str(url)
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", fake_post)

    response = client.post(
        f"{ADMIN_BASE}/model-config/test",
        headers=admin_headers,
        json={
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["model"] == "gpt-4.1-mini"
    assert response.json()["summary"] == "connection_ok"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"


def test_admin_agent_model_config_test_auto_appends_v1_suffix(client, admin_headers, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"connection_ok","needs_approval":false,"proposed_action":"approve"}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *args, **kwargs):
        captured["url"] = str(url)
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", fake_post)

    response = client.post(
        f"{ADMIN_BASE}/model-config/test",
        headers=admin_headers,
        json={
            "base_url": "https://xh.v1api.cc",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["url"] == "https://xh.v1api.cc/v1/chat/completions"


def test_admin_agent_model_config_test_rejects_empty_response_body(client, admin_headers, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        text = ""
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        def raise_for_status(self) -> None:
            return None

        def json(self):
            raise ValueError("No JSON payload")

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", lambda *args, **kwargs: FakeResponse())

    response = client.post(
        f"{ADMIN_BASE}/model-config/test",
        headers=admin_headers,
        json={
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "empty response body" in payload["summary"]
    assert "请检查 Base URL" in payload["summary"]


def test_admin_agent_model_config_test_rejects_html_response_body(client, admin_headers, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        text = "<!doctype html><html><head></head><body>not json</body></html>"
        headers: ClassVar[dict[str, str]] = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

        def json(self):
            raise ValueError("No JSON payload")

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", lambda *args, **kwargs: FakeResponse())

    response = client.post(
        f"{ADMIN_BASE}/model-config/test",
        headers=admin_headers,
        json={
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "returned HTML instead of JSON" in payload["summary"]
    assert "请检查 Base URL" in payload["summary"]


def test_admin_agent_workflow_crud_roundtrip(client, admin_headers) -> None:
    graph_payload = {
        "version": 1,
        "viewport": {"x": 0, "y": 0, "zoom": 0.92},
        "nodes": [
            {
                "id": "trigger",
                "type": "trigger",
                "label": "Trigger",
                "position": {"x": 90, "y": 120},
                "config": {
                    "primary": True,
                    "trigger_event": "comment.pending",
                    "target_type": "comment",
                },
            },
            {
                "id": "ai-task",
                "type": "ai_task",
                "label": "AI Task",
                "position": {"x": 360, "y": 120},
                "config": {
                    "primary": True,
                    "instructions": "优先识别广告和垃圾内容。",
                },
            },
            {
                "id": "approval",
                "type": "approval_gate",
                "label": "Approval",
                "position": {"x": 640, "y": 120},
                "config": {
                    "primary": True,
                    "enabled": False,
                },
            },
            {
                "id": "action",
                "type": "action",
                "label": "Action",
                "position": {"x": 910, "y": 120},
                "config": {
                    "capability": "moderate_comment",
                    "action": "approve",
                },
            },
        ],
        "edges": [
            {
                "id": "edge-trigger-ai",
                "source": "trigger",
                "target": "ai-task",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-ai-approval",
                "source": "ai-task",
                "target": "approval",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-approval-action",
                "source": "approval",
                "target": "action",
                "label": "",
                "type": "default",
                "config": {},
            },
        ],
    }

    response = client.get(f"{ADMIN_BASE}/workflows", headers=admin_headers)

    assert response.status_code == 200
    keys = {item["key"] for item in response.json()}
    assert "community_moderation_v1" in keys

    create_response = client.post(
        f"{ADMIN_BASE}/workflows",
        headers=admin_headers,
        json={
            "key": "comment_triage_fastlane",
            "name": "评论快速分流",
            "description": "给评论事件补一条更快的分流流程。",
            "trigger_event": "comment.pending",
            "target_type": "comment",
            "enabled": True,
            "require_human_approval": False,
            "instructions": "优先识别广告和垃圾内容。",
            "graph": graph_payload,
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["key"] == "comment_triage_fastlane"
    assert create_response.json()["built_in"] is False
    assert create_response.json()["graph"]["nodes"][0]["id"] == "trigger"
    assert create_response.json()["graph"]["nodes"][1]["config"]["instructions"] == "优先识别广告和垃圾内容。"

    update_response = client.put(
        f"{ADMIN_BASE}/workflows/comment_triage_fastlane",
        headers=admin_headers,
        json={
            "description": "改成默认关闭，只有需要时再开启。",
            "enabled": False,
            "require_human_approval": True,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["enabled"] is False
    assert update_response.json()["require_human_approval"] is True

    list_response = client.get(f"{ADMIN_BASE}/workflows", headers=admin_headers)
    assert list_response.status_code == 200
    created = next(item for item in list_response.json() if item["key"] == "comment_triage_fastlane")
    assert created["description"] == "改成默认关闭，只有需要时再开启。"
    assert created["graph"]["edges"][0]["source"] == "trigger"

    delete_response = client.delete(
        f"{ADMIN_BASE}/workflows/comment_triage_fastlane",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    final_response = client.get(f"{ADMIN_BASE}/workflows", headers=admin_headers)
    assert final_response.status_code == 200
    final_keys = {item["key"] for item in final_response.json()}
    assert "comment_triage_fastlane" not in final_keys


def test_admin_agent_workflow_catalog(client, admin_headers) -> None:
    response = client.get(f"{ADMIN_BASE}/workflow-catalog", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert any(item["value"] == "engagement.pending" for item in payload["trigger_events"])
    assert any(item["key"] == "moderate_comment" for item in payload["operation_catalog"])
    assert any(item["type"] == "apply.action" for item in payload["node_types"])
    assert payload["trigger_events"][0]["payload_fields"]
    assert payload["readonly_tools"]
    assert "workflow_local_action_surfaces" in payload


def test_admin_workflow_surface_draft_message_roundtrip(client, admin_headers, monkeypatch) -> None:
    config_response = client.put(
        f"{ADMIN_BASE}/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://model.example/v1",
            "model": "planning-model",
            "api_key": "secret-key",
            "temperature": 0.1,
            "timeout_seconds": 20,
            "advisory_prompt": "Return strict JSON only.",
        },
    )
    assert config_response.status_code == 200

    monkeypatch.setattr(
        "aerisun.domain.automation.surfaces.invoke_model_json",
        lambda *args, **kwargs: {
            "assistant_message": "已整理 surface 方案。",
            "summary": "新增一个执行 surface。",
            "ready_to_apply": False,
            "patches": [],
            "graph_mutation": {},
        },
    )

    response = client.post(
        f"{ADMIN_BASE}/workflows/community_moderation_v1/surface-draft/messages",
        headers=admin_headers,
        json={"message": "新增一个只允许通过当前流程查到评论的执行 surface"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["summary"] == "新增一个执行 surface。"
    assert payload["messages"][-1]["role"] == "assistant"


def test_admin_workflow_surface_draft_apply_roundtrip(client, admin_headers, monkeypatch) -> None:
    config_response = client.put(
        f"{ADMIN_BASE}/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://model.example/v1",
            "model": "planning-model",
            "api_key": "secret-key",
            "temperature": 0.1,
            "timeout_seconds": 20,
            "advisory_prompt": "Return strict JSON only.",
        },
    )
    assert config_response.status_code == 200

    monkeypatch.setattr(
        "aerisun.domain.automation.surfaces.invoke_model_json",
        lambda *args, **kwargs: {
            "assistant_message": "已整理 surface 方案。",
            "summary": "新增一个执行 surface。",
            "ready_to_apply": True,
            "patches": [
                {
                    "action": "create",
                    "surface_kind": "action_surface",
                    "surface_key": "moderate_from_flow",
                    "reason": "创建本地执行 surface",
                    "impact": "新增一个执行动作入口",
                    "human_summary": "新增一个只允许当前流程使用的审核执行 surface。",
                    "spec": {
                        "label": "按对象自动选择评论 / 留言审核",
                        "description": "根据当前对象自动选择评论审核或留言审核。",
                        "base_capability": "moderate_comment_item",
                        "action_key": "moderate_comment_item",
                        "domain": "moderation",
                        "allowed_args": ["comment_id", "entry_id", "action", "reason"],
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "comment_id": {"type": "string"},
                                "entry_id": {"type": "string"},
                                "action": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                        },
                        "ref_binding": {
                            "source": "input",
                            "path": "surface_ref",
                            "requires_surface": "",
                            "resolve_to": "",
                        },
                    },
                }
            ],
            "graph_mutation": {},
        },
    )

    draft_response = client.post(
        f"{ADMIN_BASE}/workflows/community_moderation_v1/surface-draft/messages",
        headers=admin_headers,
        json={"message": "新增一个只允许通过当前流程使用的审核执行 surface"},
    )
    assert draft_response.status_code == 200

    apply_response = client.post(
        f"{ADMIN_BASE}/workflows/community_moderation_v1/surface-draft/apply",
        headers=admin_headers,
    )

    assert apply_response.status_code == 200
    payload = apply_response.json()
    assert payload["ok"] is True
    assert payload["workflow"]["key"] == "community_moderation_v1"
    surface_keys = [item["key"] for item in payload["catalog"]["workflow_local_action_surfaces"]]
    assert "moderate_from_flow" in surface_keys


def test_admin_workflow_surface_draft_legacy_multistep_spec_is_marked_not_ready(
    client, admin_headers, monkeypatch
) -> None:
    config_response = client.put(
        f"{ADMIN_BASE}/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://model.example/v1",
            "model": "planning-model",
            "api_key": "secret-key",
            "temperature": 0.1,
            "timeout_seconds": 20,
            "advisory_prompt": "Return strict JSON only.",
        },
    )
    assert config_response.status_code == 200

    monkeypatch.setattr(
        "aerisun.domain.automation.surfaces.invoke_model_json",
        lambda *args, **kwargs: {
            "assistant_message": "已整理 surface 方案。",
            "summary": "创建一个修改最新文章的执行 surface。",
            "ready_to_apply": True,
            "patches": [
                {
                    "action": "create",
                    "surface_kind": "action_surface",
                    "surface_key": "update_latest_post",
                    "reason": "创建执行 surface",
                    "impact": "修改最新文章",
                    "human_summary": "修改最新文章",
                    "spec": {
                        "name": "修改最新文章",
                        "description": "先取最新文章，再修改它",
                        "scopes": ["content:read", "content:write"],
                        "input_schema": {
                            "type": "object",
                            "properties": {"new_content": {"type": "string"}},
                            "required": ["new_content"],
                        },
                        "steps": [
                            {"id": "get_latest_posts", "invocation": {"tool": "list_admin_content"}},
                            {"id": "update_post", "invocation": {"tool": "update_admin_content"}},
                        ],
                    },
                }
            ],
            "graph_mutation": {},
        },
    )

    response = client.post(
        f"{ADMIN_BASE}/workflows/community_moderation_v1/surface-draft/messages",
        headers=admin_headers,
        json={"message": "创建一个修改最新文章的执行 surface"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready_to_apply"] is False
    assert any("旧的多步骤格式" in issue for issue in payload["validation_issues"])


def test_bundle_action_surface_invocations_expand_and_execute(seeded_session, monkeypatch) -> None:
    workflow = get_agent_workflow(seeded_session, "community_moderation_v1")
    pack = load_workflow_pack(workflow.key)
    bundle_surface = ActionSurfaceSpec(
        key="post_management",
        surface_mode="bundle",
        label="文章管理",
        description="一组文章管理动作",
        domain="content",
        entries=[
            ActionSurfaceEntrySpec(
                key="update_post",
                label="修改文章",
                description="修改指定文章",
                action_key="update_admin_content",
                base_capability="update_admin_content",
                fixed_args={"content_type": "posts"},
                allowed_args=["item_id", "payload"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                        "payload": {"type": "object"},
                    },
                    "required": ["item_id", "payload"],
                },
            ),
            ActionSurfaceEntrySpec(
                key="create_post",
                label="创建文章",
                description="创建一篇新文章",
                action_key="create_admin_content",
                base_capability="create_admin_content",
                fixed_args={"content_type": "posts"},
                allowed_args=["payload"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "payload": {"type": "object"},
                    },
                    "required": ["payload"],
                },
            ),
        ],
    )
    write_workflow_pack(
        workflow=workflow,
        query_surfaces=pack.query_surfaces,
        action_surfaces=[*pack.action_surfaces, bundle_surface],
        built_in=pack.manifest.built_in,
    )

    invocations = list_action_surface_invocations(workflow.key, surface_keys=["post_management"])
    invocation_keys = {item.key for item in invocations}
    assert "post_management#update_post" in invocation_keys
    assert "post_management#create_post" in invocation_keys

    captured: dict[str, object] = {}

    def fake_execute_capability(session, *, kind: str, name: str, **kwargs):
        captured["kind"] = kind
        captured["name"] = name
        captured["kwargs"] = kwargs
        return {"ok": True, "name": name, "kwargs": kwargs}

    monkeypatch.setattr("aerisun.domain.automation.tool_surface.execute_capability", fake_execute_capability)

    result = execute_action_surface(
        seeded_session,
        "post_management#update_post",
        workflow_key=workflow.key,
        run_id="run-bundle",
        input_payload={"item_id": "post-1", "payload": {"body": "new body"}},
        bound_values={},
    )

    assert captured["kind"] == "tool"
    assert captured["name"] == "update_admin_content"
    assert captured["kwargs"] == {
        "content_type": "posts",
        "item_id": "post-1",
        "payload": {"body": "new body"},
    }
    assert result["ok"] is True


def test_bundle_action_surface_mounts_expose_entry_actions_to_ai_contract_context(seeded_session) -> None:
    workflow = get_agent_workflow(seeded_session, "community_moderation_v1")
    pack = load_workflow_pack(workflow.key)
    bundle_surface = ActionSurfaceSpec(
        key="post_management",
        surface_mode="bundle",
        label="文章管理",
        description="一组文章管理动作",
        domain="content",
        entries=[
            ActionSurfaceEntrySpec(
                key="update_post",
                label="修改文章",
                description="修改指定文章",
                action_key="update_admin_content",
                base_capability="update_admin_content",
                fixed_args={"content_type": "posts"},
                allowed_args=["item_id", "payload"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                        "payload": {"type": "object"},
                    },
                    "required": ["item_id", "payload"],
                },
            )
        ],
    )
    graph = AgentWorkflowGraph(
        version=2,
        nodes=[
            {
                "id": "ai-1",
                "type": "ai.task",
                "label": "AI Task",
                "position": {"x": 120, "y": 120},
                "config": {"instructions": "test"},
            },
            {
                "id": "action-1",
                "type": "apply.action",
                "label": "Post Action",
                "position": {"x": 120, "y": 20},
                "config": {"surface_key": "post_management"},
            },
        ],
        edges=[
            {
                "id": "edge-action-ai",
                "source": "action-1",
                "target": "ai-1",
                "source_handle": "action",
                "target_handle": "mount_1",
                "type": "default",
                "config": {"kind": "action"},
            }
        ],
        viewport={"x": 0, "y": 0, "zoom": 1},
    )
    workflow = workflow.model_copy(update={"graph": graph})
    write_workflow_pack(
        workflow=workflow,
        query_surfaces=pack.query_surfaces,
        action_surfaces=[*pack.action_surfaces, bundle_surface],
        built_in=pack.manifest.built_in,
    )

    contract = build_ai_contract_context(
        workflow_key=workflow.key,
        workflow_config=workflow.model_dump(mode="json"),
        ai_node_id="ai-1",
        node_config={"instructions": "test"},
    )

    mounted_action_keys = {item["key"] for item in contract["mounted_actions"]}
    assert "post_management#update_post" in mounted_action_keys


def test_emit_comment_pending_uses_dynamic_workflow_mapping(seeded_session) -> None:
    update_agent_workflow(
        seeded_session,
        workflow_key="community_moderation_v1",
        payload=AgentWorkflowUpdate(enabled=False),
    )
    create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="comment_triage_fastlane",
            name="评论快速分流",
            description="用于验证动态工作流映射。",
            trigger_event="comment.pending",
            target_type="comment",
            enabled=True,
            require_human_approval=False,
            instructions="把明显安全的内容直接标记为 approve。",
        ),
    )

    emit_comment_pending(
        seeded_session,
        comment_id="comment-1",
        content_type="posts",
        content_slug="hello-world",
        author_name="Rowan",
        body_preview="A pending comment body.",
    )

    runs = list_runs(seeded_session)
    assert len(runs) == 1
    assert runs[0].workflow_key == "comment_triage_fastlane"
    assert runs[0].trigger_event == "comment.pending"


def test_emit_guestbook_pending_uses_shared_community_workflow(seeded_session) -> None:
    emit_guestbook_pending(
        seeded_session,
        entry_id="guestbook-1",
        author_name="Rowan",
        body_preview="A pending guestbook message.",
    )

    runs = list_runs(seeded_session)
    assert len(runs) == 1
    assert runs[0].workflow_key == "community_moderation_v1"
    assert runs[0].trigger_event == "guestbook.pending"


def test_execute_due_runs_uses_model_config(seeded_session, tmp_path, monkeypatch) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            provider="openai_compatible",
            base_url="https://model.example/v1",
            model="moderation-model",
            api_key="secret-key",
            temperature=0.1,
            timeout_seconds=12,
            advisory_prompt="Return strict JSON only.",
        ),
    )

    emit_comment_pending(
        seeded_session,
        comment_id="comment-llm-1",
        content_type="posts",
        content_slug="hello-world",
        author_name="Rowan",
        body_preview="Needs moderation review.",
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"LLM review summary","needs_approval":true,"proposed_action":"reject"}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", lambda *args, **kwargs: FakeResponse())

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "workflow.sqlite")
    runtime.start()
    try:
        processed = execute_due_runs(seeded_session, runtime)
    finally:
        runtime.stop()

    approvals = list_pending_approvals(seeded_session)
    assert processed == 1
    assert len(approvals) == 1
    assert approvals[0].request_payload["value"]["message"] == "LLM review summary"


def test_execute_due_runs_respects_condition_branching_from_graph(seeded_session, tmp_path, monkeypatch) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            provider="openai_compatible",
            base_url="https://model.example/v1",
            model="moderation-model",
            api_key="secret-key",
            temperature=0.1,
            timeout_seconds=12,
            advisory_prompt="Return strict JSON only.",
        ),
    )

    graph_payload = {
        "version": 1,
        "viewport": {"x": 0, "y": 0, "zoom": 0.92},
        "nodes": [
            {
                "id": "trigger-primary",
                "type": "trigger",
                "label": "Trigger",
                "position": {"x": 90, "y": 120},
                "config": {
                    "primary": True,
                    "trigger_event": "comment.pending",
                    "target_type": "comment",
                },
            },
            {
                "id": "ai-primary",
                "type": "ai_task",
                "label": "AI Task",
                "position": {"x": 350, "y": 120},
                "config": {
                    "primary": True,
                    "instructions": "根据评论内容返回 approve 或 reject。",
                },
            },
            {
                "id": "condition-branch",
                "type": "condition",
                "label": "Condition",
                "position": {"x": 610, "y": 120},
                "config": {
                    "expression": 'proposed_action == "approve"',
                },
            },
            {
                "id": "action-approve",
                "type": "action",
                "label": "Approve Path",
                "position": {"x": 900, "y": 40},
                "config": {
                    "capability": "moderate_comment",
                    "action": "approve",
                },
            },
            {
                "id": "action-reject",
                "type": "action",
                "label": "Reject Path",
                "position": {"x": 900, "y": 220},
                "config": {
                    "capability": "moderate_comment",
                    "action": "reject",
                    "fallback_mode": "pending_on_ai_reject",
                },
            },
        ],
        "edges": [
            {
                "id": "edge-trigger-ai",
                "source": "trigger-primary",
                "target": "ai-primary",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-ai-condition",
                "source": "ai-primary",
                "target": "condition-branch",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-condition-true",
                "source": "condition-branch",
                "target": "action-approve",
                "label": "true",
                "type": "default",
                "config": {"match": "true"},
            },
            {
                "id": "edge-condition-false",
                "source": "condition-branch",
                "target": "action-reject",
                "label": "false",
                "type": "default",
                "config": {"match": "false"},
            },
        ],
    }

    update_agent_workflow(
        seeded_session,
        workflow_key="community_moderation_v1",
        payload=AgentWorkflowUpdate(
            trigger_event="comment.pending",
            target_type="comment",
            enabled=True,
            require_human_approval=False,
            instructions="根据评论内容返回 approve 或 reject。",
            graph=graph_payload,
        ),
    )

    settings = get_settings()
    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waiting_comment(
            connection,
            url="/posts/hello-world",
            nick="Branching Reader",
            comment="Looks friendly and safe.",
            created_at="2026-03-25 12:00:00",
        )
        connection.commit()

    emit_comment_pending(
        seeded_session,
        comment_id=str(comment_id),
        content_type="posts",
        content_slug="hello-world",
        author_name="Branching Reader",
        body_preview="Looks friendly and safe.",
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": ('{"summary":"Looks safe","needs_approval":false,"proposed_action":"approve"}')
                        }
                    }
                ]
            }

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", lambda *args, **kwargs: FakeResponse())

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "workflow-graph.sqlite")
    runtime.start()
    try:
        processed = execute_due_runs(seeded_session, runtime)
    finally:
        runtime.stop()

    runs = list_runs(seeded_session)
    assert processed == 1
    assert runs[0].status == "completed"
    assert runs[0].result_payload["action"] == "approve"
    assert runs[0].result_payload["applied"] is True
    assert "action-approve" in runs[0].result_payload["graph_execution"]["completed_nodes"]
    assert "action-reject" not in runs[0].result_payload["graph_execution"]["completed_nodes"]

    _run, steps = get_run_detail(seeded_session, runs[0].id)
    node_keys = [step.node_key for step in steps]
    assert "condition-branch" in node_keys
    assert "action-approve" in node_keys
    assert "action-reject" not in node_keys


def test_auto_reject_is_deferred_to_pending_for_manual_review(seeded_session, tmp_path, monkeypatch) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            provider="openai_compatible",
            base_url="https://model.example/v1",
            model="moderation-model",
            api_key="secret-key",
            temperature=0.1,
            timeout_seconds=12,
            advisory_prompt="Return strict JSON only.",
        ),
    )

    settings = get_settings()
    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waiting_comment(
            connection,
            url="/posts/hello-world",
            nick="Needs Human Review",
            comment="Please moderate this sensitive comment.",
            created_at="2026-03-23 12:00:00",
        )
        connection.commit()

    emit_comment_pending(
        seeded_session,
        comment_id=str(comment_id),
        content_type="posts",
        content_slug="hello-world",
        author_name="Needs Human Review",
        body_preview="Please moderate this sensitive comment.",
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": ('{"summary":"Looks risky","needs_approval":false,"proposed_action":"reject"}')
                        }
                    }
                ]
            }

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", lambda *args, **kwargs: FakeResponse())

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "workflow-auto-reject.sqlite")
    runtime.start()
    try:
        processed = execute_due_runs(seeded_session, runtime)
    finally:
        runtime.stop()

    approvals = list_pending_approvals(seeded_session)
    runs = list_runs(seeded_session)
    assert processed == 1
    assert approvals == []
    assert runs[0].status == "completed"
    assert runs[0].result_payload["action"] == "pending"
    assert runs[0].result_payload["applied"] is False
    assert runs[0].result_payload["execution"]["capability"] == "moderation_deferred"

    with connect_waline_db(settings.waline_db_path) as connection:
        row = connection.execute("SELECT status FROM wl_comment WHERE id = ?", (comment_id,)).fetchone()
        assert row is not None
        assert row["status"] == "waiting"


def test_execute_due_runs_cancels_when_model_is_disabled(seeded_session, tmp_path) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=False,
            provider="openai_compatible",
            base_url="https://model.example/v1",
            model="moderation-model",
            api_key="secret-key",
        ),
    )

    emit_comment_pending(
        seeded_session,
        comment_id="comment-disabled-1",
        content_type="posts",
        content_slug="hello-world",
        author_name="Rowan",
        body_preview="Should not run while the model is disabled.",
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "workflow-disabled.sqlite")
    runtime.start()
    try:
        processed = execute_due_runs(seeded_session, runtime)
    finally:
        runtime.stop()

    runs = list_runs(seeded_session)
    assert processed == 1
    assert runs[0].status == "cancelled"
    assert runs[0].result_payload["reason"] == "model_disabled"


def test_comment_pending_run_can_apply_approval_and_emit_moderated_event(
    seeded_session,
    tmp_path,
    monkeypatch,
    admin_user,
) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            provider="openai_compatible",
            base_url="https://model.example/v1",
            model="moderation-model",
            api_key="secret-key",
            temperature=0.1,
            timeout_seconds=12,
            advisory_prompt="Return strict JSON only.",
        ),
    )
    create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="comment-approved-hook",
            target_url="https://example.com/webhook",
            event_types=["comment.approve"],
            status="active",
            timeout_seconds=10,
            max_attempts=3,
        ),
    )

    settings = get_settings()
    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waiting_comment(
            connection,
            url="/posts/hello-world",
            nick="Pending Reader",
            comment="Please approve this comment.",
            created_at="2026-03-21 12:00:00",
        )
        connection.commit()

    emit_comment_pending(
        seeded_session,
        comment_id=str(comment_id),
        content_type="posts",
        content_slug="hello-world",
        author_name="Pending Reader",
        body_preview="Please approve this comment.",
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"Looks safe to approve","needs_approval":true,"proposed_action":"approve"}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", lambda *args, **kwargs: FakeResponse())

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "workflow.sqlite")
    runtime.start()
    try:
        processed = execute_due_runs(seeded_session, runtime)
        approvals = list_pending_approvals(seeded_session)
        assert processed == 1
        assert len(approvals) == 1

        run = resolve_approval(
            seeded_session,
            runtime,
            approval_id=approvals[0].id,
            actor_id=admin_user.id,
            decision_payload=ApprovalDecisionWrite(action="approve", reason="manual_confirmed"),
        )
    finally:
        runtime.stop()

    with connect_waline_db(settings.waline_db_path) as connection:
        row = connection.execute("SELECT status FROM wl_comment WHERE id = ?", (comment_id,)).fetchone()
        assert row is not None
        assert row["status"] == "approved"

    deliveries = list_webhook_deliveries(seeded_session)
    assert run.status == "completed"
    assert run.result_payload["applied"] is True
    assert run.result_payload["execution"]["capability"] == "moderate_comment"
    assert any(
        item.event_type == "comment.approve" and item.payload.get("payload", {}).get("comment_id") == str(comment_id)
        for item in deliveries
    )


def test_admin_workflow_catalog_exposes_v2_node_and_operation_registry(client, admin_headers) -> None:
    response = client.get(f"{ADMIN_BASE}/workflow-catalog", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    node_types = {item["type"] for item in payload["node_types"]}
    trigger_types = {item["type"] for item in payload["trigger_types"]}
    operation_keys = {item["key"] for item in payload["operation_catalog"]}

    assert "ai.task" in node_types
    assert "operation.capability" in node_types
    assert "trigger.schedule" in trigger_types
    assert "moderate_comment" in operation_keys
    assert "update_admin_content" in operation_keys
    assert "list_admin_content" in operation_keys


def test_admin_workflow_validate_rejects_cycles(client, admin_headers) -> None:
    response = client.post(
        f"{ADMIN_BASE}/workflows/validate",
        headers=admin_headers,
        json={
            "key": "cycle-test",
            "name": "Cycle Test",
            "description": "graph cycle should be rejected",
            "enabled": True,
            "schema_version": 2,
            "trigger_bindings": [
                {
                    "id": "manual-trigger",
                    "type": "trigger.manual",
                    "label": "Manual Trigger",
                    "enabled": True,
                    "config": {},
                }
            ],
            "runtime_policy": {
                "approval_mode": "risk_based",
                "allow_high_risk_without_approval": False,
                "max_steps": 20,
            },
            "graph": {
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "noop",
                        "type": "operation.capability",
                        "label": "Noop",
                        "position": {"x": 240, "y": 0},
                        "config": {"operation_key": "noop"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "trigger",
                        "target": "noop",
                        "label": "",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-2",
                        "source": "noop",
                        "target": "trigger",
                        "label": "",
                        "type": "default",
                        "config": {},
                    },
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert any(item["code"] == "graph.cycle_not_supported" for item in payload["issues"])


def test_admin_workflow_manual_run_endpoint_executes_v2_graph(client, admin_headers) -> None:
    create_response = client.post(
        f"{ADMIN_BASE}/workflows",
        headers=admin_headers,
        json={
            "key": "manual_noop_v2",
            "name": "Manual Noop",
            "description": "A minimal v2 workflow.",
            "enabled": True,
            "schema_version": 2,
            "trigger_bindings": [
                {
                    "id": "manual-trigger",
                    "type": "trigger.manual",
                    "label": "Manual Trigger",
                    "enabled": True,
                    "config": {},
                }
            ],
            "runtime_policy": {
                "approval_mode": "risk_based",
                "allow_high_risk_without_approval": False,
                "max_steps": 20,
            },
            "graph": {
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "noop",
                        "type": "operation.capability",
                        "label": "Noop",
                        "position": {"x": 240, "y": 0},
                        "config": {"operation_key": "noop"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "trigger",
                        "target": "noop",
                        "label": "",
                        "type": "default",
                        "config": {},
                    },
                ],
            },
        },
    )

    assert create_response.status_code == 201

    run_response = client.post(
        f"{ADMIN_BASE}/workflows/manual_noop_v2/runs",
        headers=admin_headers,
        json={
            "trigger_binding_id": "manual-trigger",
            "context_payload": {"source": "test"},
            "execute_immediately": True,
        },
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["run"]["status"] == "completed"
    assert payload["run"]["result_payload"]["execution"]["capability"] == "noop"
    assert any(step["node_key"] == "noop" for step in payload["steps"])


def test_public_webhook_trigger_endpoint_runs_bound_workflow(client, admin_headers) -> None:
    create_response = client.post(
        f"{ADMIN_BASE}/workflows",
        headers=admin_headers,
        json={
            "key": "webhook_noop_v2",
            "name": "Webhook Noop",
            "description": "A webhook-triggered v2 workflow.",
            "enabled": True,
            "schema_version": 2,
            "trigger_bindings": [
                {
                    "id": "incoming-hook",
                    "type": "trigger.webhook",
                    "label": "Incoming Hook",
                    "enabled": True,
                    "config": {"path": "incoming/hook", "secret": "dev-secret"},
                }
            ],
            "runtime_policy": {
                "approval_mode": "risk_based",
                "allow_high_risk_without_approval": False,
                "max_steps": 20,
            },
            "graph": {
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.webhook",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "noop",
                        "type": "operation.capability",
                        "label": "Noop",
                        "position": {"x": 240, "y": 0},
                        "config": {"operation_key": "noop"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "trigger",
                        "target": "noop",
                        "label": "",
                        "type": "default",
                        "config": {},
                    },
                ],
            },
        },
    )
    assert create_response.status_code == 201

    response = client.post(
        "/api/v1/automation/webhook-triggers/webhook_noop_v2/incoming-hook?token=dev-secret",
        json={"target_id": "webhook-target", "payload": {"hello": "world"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["run"]["status"] == "completed"


def test_workflow_definition_is_persisted_as_pack(seeded_session) -> None:
    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="pack_storage_demo",
            name="Pack Storage Demo",
            description="Persist through workflow pack files.",
            trigger_bindings=[
                {
                    "id": "manual-trigger",
                    "type": "trigger.manual",
                    "label": "Manual",
                    "enabled": True,
                    "config": {},
                }
            ],
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "noop",
                        "type": "operation.capability",
                        "label": "Noop",
                        "position": {"x": 240, "y": 0},
                        "config": {"operation_key": "noop"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "trigger",
                        "target": "noop",
                        "label": "",
                        "type": "default",
                        "config": {},
                    },
                ],
            },
        ),
    )

    pack_dir = workflow_pack_path(workflow.key)
    assert pack_dir.exists()
    assert (pack_dir / "manifest.yaml").exists()
    assert (pack_dir / "workflow.graph.json").exists()
    assert (pack_dir / "README.generated.md").exists()

    profile = site_repo.find_site_profile(seeded_session)
    assert profile is not None
    assert "agent_workflows" not in dict(profile.feature_flags or {})


def test_workflow_catalog_scopes_surfaces_to_current_pack(seeded_session) -> None:
    workflow_a = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="surface_scope_a",
            name="Surface Scope A",
            description="A",
            trigger_bindings=[
                {"id": "manual-a", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger-a",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "note-a",
                        "type": "note",
                        "label": "Note",
                        "position": {"x": 240, "y": 0},
                        "config": {"content": "A"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-a",
                        "source": "trigger-a",
                        "target": "note-a",
                        "label": "",
                        "type": "default",
                        "config": {},
                    }
                ],
            },
        ),
    )
    workflow_b = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="surface_scope_b",
            name="Surface Scope B",
            description="B",
            trigger_bindings=[
                {"id": "manual-b", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger-b",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "note-b",
                        "type": "note",
                        "label": "Note",
                        "position": {"x": 240, "y": 0},
                        "config": {"content": "B"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-b",
                        "source": "trigger-b",
                        "target": "note-b",
                        "label": "",
                        "type": "default",
                        "config": {},
                    }
                ],
            },
        ),
    )
    write_workflow_pack(
        workflow=workflow_a,
        query_surfaces=[
            QuerySurfaceSpec(
                key="posts.latest_for_a",
                label="A Query",
                description="Only for pack A",
                base_capability="list_admin_content",
                fixed_args={"content_type": "posts", "page": 1, "page_size": 5},
                output_projection={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "object", "properties": {"id": {"type": "string"}}},
                        }
                    },
                },
            )
        ],
    )
    write_workflow_pack(
        workflow=workflow_b,
        query_surfaces=[
            QuerySurfaceSpec(
                key="posts.latest_for_b",
                label="B Query",
                description="Only for pack B",
                base_capability="list_admin_content",
                fixed_args={"content_type": "posts", "page": 1, "page_size": 5},
                output_projection={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "object", "properties": {"id": {"type": "string"}}},
                        }
                    },
                },
            )
        ],
    )

    catalog_a = build_workflow_catalog(seeded_session, workflow_key=workflow_a.key)
    catalog_b = build_workflow_catalog(seeded_session, workflow_key=workflow_b.key)

    catalog_a_keys = [item.key for item in catalog_a.readonly_tools]
    catalog_b_keys = [item.key for item in catalog_b.readonly_tools]

    assert "posts.latest_for_a" not in catalog_a_keys
    assert "posts.latest_for_b" not in catalog_a_keys
    assert "posts.latest_for_b" not in catalog_b_keys
    assert "posts.latest_for_a" not in catalog_b_keys
    assert "observe.moderation.comments.list" in catalog_a_keys
    assert "observe.moderation.comments.list" in catalog_b_keys


def test_surface_ref_only_allows_current_run_and_allowed_query(seeded_session) -> None:
    with connect_waline_db() as waline:
        comment_id = _seed_waiting_comment(
            waline,
            url="/posts/surface-ref",
            nick="Surface Ref",
            comment="Please moderate me",
            created_at="2026-03-31T10:00:00.000Z",
        )
    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="surface_ref_demo",
            name="Surface Ref Demo",
            description="Action surfaces must consume opaque refs.",
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "note",
                        "type": "note",
                        "label": "Note",
                        "position": {"x": 240, "y": 0},
                        "config": {"content": "surface ref"},
                    },
                ],
                "edges": [
                    {"id": "edge", "source": "trigger", "target": "note", "label": "", "type": "default", "config": {}}
                ],
            },
        ),
    )
    write_workflow_pack(
        workflow=workflow,
        query_surfaces=[
            QuerySurfaceSpec(
                key="comments.latest_pending",
                label="最新评论待审核",
                description="只读取待审核评论。",
                base_capability="list_comment_moderation_queue",
                fixed_args={"page": 1, "page_size": 10},
                output_projection={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "comment_id": {"type": "string"},
                                    "author_name": {"type": "string"},
                                    "body_preview": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                ref_resource="comment",
                ref_id_field="comment_id",
                allowed_action_keys=["comments.approve_selected"],
            )
        ],
        action_surfaces=[
            ActionSurfaceSpec(
                key="comments.approve_selected",
                label="通过所选评论",
                description="只能通过本次查询结果中的评论。",
                base_capability="moderate_comment",
                fixed_args={"action": "approve"},
                bound_args={"reason": SurfaceBoundArgConfig(source="input", path="reason")},
                allowed_source_query_keys=["comments.latest_pending"],
                ref_binding=SurfaceRefBindingConfig(path="surface_ref", resolve_to="comment_id"),
            )
        ],
    )

    result = execute_tool_surface(
        seeded_session,
        "comments.latest_pending",
        workflow_key=workflow.key,
        run_id="run-surface-ref-1",
    )
    items = list((result or {}).get("items") or [])
    target = next((item for item in items if str(item.get("comment_id")) == str(comment_id)), None)
    assert target is not None
    surface_ref = str(target.get("surface_ref") or "")
    assert surface_ref

    action_result = execute_action_surface(
        seeded_session,
        "comments.approve_selected",
        workflow_key=workflow.key,
        run_id="run-surface-ref-1",
        input_payload={"surface_ref": surface_ref, "reason": "looks good"},
    )
    assert isinstance(action_result, dict)

    try:
        execute_action_surface(
            seeded_session,
            "comments.approve_selected",
            workflow_key=workflow.key,
            run_id="run-surface-ref-2",
            input_payload={"surface_ref": surface_ref, "reason": "wrong run"},
        )
    except ValidationError as exc:
        assert "different run" in str(exc)
    else:  # pragma: no cover - defensive expectation
        raise AssertionError("surface_ref should reject a different run_id")


def test_ai_shell_input_payload_includes_trigger_context_payload() -> None:
    payload = _ai_shell_input_payload(
        {
            "trigger_event": "content.updated",
            "target_type": "content",
            "target_id": "content-123",
            "inputs": {"manual_reason": "qa"},
            "context_payload": {
                "content_type": "posts",
                "content_id": "content-123",
                "changed_fields": ["title"],
            },
            "node_outputs": {},
            "artifacts": {},
            "workflow_config": {
                "graph": {
                    "nodes": [
                        {"id": "trigger", "type": "trigger.event", "config": {}},
                        {"id": "ai", "type": "ai.task", "config": {}},
                    ],
                    "edges": [
                        {
                            "id": "edge-trigger-ai",
                            "source": "trigger",
                            "target": "ai",
                            "target_handle": "mount_1",
                            "config": {"kind": "trigger"},
                        }
                    ],
                }
            },
        },
        {},
        node_id="ai",
    )

    assert payload["context_payload"]["content_type"] == "posts"
    assert payload["context_payload"]["changed_fields"] == ["title"]
    assert payload["trigger_inputs"]["manual_reason"] == "qa"
    assert payload["mounted_trigger"]["context_payload"]["content_type"] == "posts"
    assert payload["mounted_trigger"]["inputs"]["manual_reason"] == "qa"


def test_execute_tool_surface_autofills_content_context(client, admin_headers, seeded_session) -> None:
    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "autofill-tool-surface",
            "title": "Autofill Tool Surface",
            "body": "Initial body",
            "status": "draft",
            "visibility": "public",
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    result = execute_tool_surface(
        seeded_session,
        "observe.content.admin_items.get",
        workflow_key="autofill-tool-surface-demo",
        run_id="run-autofill-tool-1",
        agent_args={},
        bound_values={
            "input": {
                "context_payload": {
                    "content_type": "posts",
                    "content_id": item["id"],
                },
                "mounted_trigger": {
                    "target_type": "content",
                    "target_id": item["id"],
                    "context_payload": {
                        "content_type": "posts",
                        "content_id": item["id"],
                    },
                },
            },
            "state": {
                "target_type": "content",
                "target_id": item["id"],
                "context_payload": {
                    "content_type": "posts",
                    "content_id": item["id"],
                },
            },
        },
    )

    assert result["id"] == item["id"]
    assert result["title"] == "Autofill Tool Surface"


def test_execute_tool_surface_normalizes_stringified_content_type(client, admin_headers, seeded_session) -> None:
    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "normalized-tool-surface",
            "title": "Normalized Tool Surface",
            "body": "Initial body",
            "status": "draft",
            "visibility": "public",
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    result = execute_tool_surface(
        seeded_session,
        "observe.content.admin_items.get",
        workflow_key="normalized-tool-surface-demo",
        run_id="run-normalized-tool-1",
        agent_args={"content_type": '{"type": "posts"}', "item_id": "wrong-item-id"},
        bound_values={
            "input": {
                "context_payload": {
                    "content_type": "posts",
                    "content_id": item["id"],
                },
            },
            "state": {
                "target_type": "content",
                "target_id": item["id"],
                "context_payload": {
                    "content_type": "posts",
                    "content_id": item["id"],
                },
            },
        },
    )

    assert result["id"] == item["id"]
    assert result["title"] == "Normalized Tool Surface"


def test_literal_string_annotation_schema_includes_type() -> None:
    from typing import Literal

    schema = _json_schema_for_annotation(Literal["posts", "diary"])
    assert schema == {
        "type": "string",
        "enum": ["posts", "diary"],
    }


def test_effective_model_timeout_expands_for_tool_rounds() -> None:
    timeout = _effective_model_timeout_seconds(
        configured_timeout_seconds=20,
        messages=[{"role": "user", "content": "read current admin content"}],
        tools=[{"type": "function", "function": {"name": "observe.content.admin_items.get"}}],
    )

    assert timeout >= 45


def test_execute_action_surface_autofills_content_context(client, admin_headers, seeded_session) -> None:
    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "autofill-action-surface",
            "title": "Autofill Action Surface",
            "body": "Initial body",
            "status": "draft",
            "visibility": "public",
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    result = execute_action_surface(
        seeded_session,
        "update_admin_content",
        workflow_key="autofill-action-surface-demo",
        run_id="run-autofill-action-1",
        input_payload={"payload": {"title": "Updated Through Autofill"}},
        bound_values={
            "input": {
                "context_payload": {
                    "content_type": "posts",
                    "content_id": item["id"],
                },
                "mounted_trigger": {
                    "target_type": "content",
                    "target_id": item["id"],
                    "context_payload": {
                        "content_type": "posts",
                        "content_id": item["id"],
                    },
                },
            },
            "state": {
                "target_type": "content",
                "target_id": item["id"],
                "context_payload": {
                    "content_type": "posts",
                    "content_id": item["id"],
                },
            },
        },
    )

    assert result["id"] == item["id"]
    assert result["title"] == "Updated Through Autofill"

    read_response = client.get(f"/api/v1/admin/posts/{item['id']}", headers=admin_headers)
    assert read_response.status_code == 200
    assert read_response.json()["title"] == "Updated Through Autofill"


def test_required_tool_usage_policy_counts_only_successful_calls() -> None:
    try:
        _enforce_tool_usage_policy(
            node_config={"tool_usage_mode": "required", "minimum_tool_calls": 1},
            tool_keys=["observe.content.admin_items.get"],
            action_keys=[],
            tool_call_results=[{"name": "observe.content.admin_items.get", "error": "execution_failed"}],
        )
    except ValidationError as exc:
        assert "successful capability call" in str(exc)
    else:  # pragma: no cover - defensive expectation
        raise AssertionError("required tool usage policy should reject failed tool calls")


def test_required_tool_usage_policy_applies_to_mounted_actions_too() -> None:
    try:
        _enforce_tool_usage_policy(
            node_config={"tool_usage_mode": "required", "minimum_tool_calls": 1},
            tool_keys=[],
            action_keys=["safe_update_post"],
            tool_call_results=[],
        )
    except ValidationError as exc:
        assert "successful capability call" in str(exc)
    else:  # pragma: no cover - defensive expectation
        raise AssertionError("required tool usage policy should reject missing mounted action calls")


def test_direct_mode_reprompts_until_required_mounted_action_is_called(
    seeded_session,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="direct_mode_action_retry_v2",
            name="Direct Mode Action Retry",
            description="Direct mode should reprompt if the model skips required mounted actions.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 360, "y": 0},
                        "config": {
                            "instructions": "必须调用 safe_create_post 创建文章。",
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "action": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "execution_summary": {"type": "string"},
                                    "execution_result": {"type": "object", "additionalProperties": True},
                                },
                                "required": [
                                    "summary",
                                    "route",
                                    "action",
                                    "reason",
                                    "execution_summary",
                                    "execution_result",
                                ],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    }
                ],
            },
        ),
    )
    pack = load_workflow_pack(workflow.key)
    write_workflow_pack(
        workflow=workflow,
        query_surfaces=list(pack.query_surfaces),
        action_surfaces=[
            *pack.action_surfaces,
            ActionSurfaceSpec(
                key="safe_create_post",
                label="Safe Create Post",
                description="Create a post for retry enforcement.",
                base_capability="create_admin_content",
                fixed_args={"content_type": "posts"},
                allowed_args=["payload"],
                input_schema={"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]},
                requires_approval=False,
            ),
        ],
        built_in=pack.manifest.built_in,
    )
    workflow = update_agent_workflow(
        seeded_session,
        workflow_key=workflow.key,
        payload=AgentWorkflowUpdate(
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "action",
                        "type": "apply.action",
                        "label": "Action",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_key": "safe_create_post"},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 360, "y": 0},
                        "config": {
                            "instructions": "必须调用 safe_create_post 创建文章。",
                            "tool_usage_mode": "required",
                            "minimum_tool_calls": 1,
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "action": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "execution_summary": {"type": "string"},
                                    "execution_result": {"type": "object", "additionalProperties": True},
                                },
                                "required": [
                                    "summary",
                                    "route",
                                    "action",
                                    "reason",
                                    "execution_summary",
                                    "execution_result",
                                ],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-action-ai",
                        "source": "action",
                        "target": "ai",
                        "source_handle": "action",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "action"},
                    },
                ],
            }
        ),
    )

    captured_messages: list[list[dict[str, Any]]] = []
    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            {
                "summary": "我已经完成创建。",
                "route": "done",
                "action": "create",
                "reason": "premature",
                "execution_summary": "伪造的执行摘要。",
                "execution_result": {"status": "fake"},
            },
            {
                "tool_calls": [
                    {
                        "name": "safe_create_post",
                        "arguments": {
                            "payload": {
                                "slug": "direct-mode-action-retry",
                                "title": "Direct Mode Action Retry",
                                "body": "Created after correction.",
                                "status": "draft",
                                "visibility": "public",
                            }
                        },
                    }
                ]
            },
            {
                **_final_output_tool_call(
                    {
                        "summary": "已在纠正后完成真实创建。",
                        "route": "done",
                        "action": "create",
                        "reason": "corrected",
                        "execution_summary": "safe_create_post 已成功执行。",
                        "execution_result": {
                            "status": "success",
                            "title": "Direct Mode Action Retry",
                        },
                    }
                )
            },
        ],
        captured_messages=captured_messages,
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "direct-mode-action-retry.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                context_payload={"probe": "direct-mode-action-retry"},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    tool_calls = list(ai_step.output_payload.get("__tool_call_results__") or [])

    assert run.status == "completed"
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "safe_create_post"
    correction_prompt_seen = any(
        any(
            "must call one of the mounted actions now" in str(message.get("content") or "")
            for message in batch
            if message.get("role") == "user"
        )
        for batch in captured_messages
    )
    assert correction_prompt_seen is True

    delete_agent_workflow(seeded_session, workflow_key=workflow.key)
    seeded_session.commit()


def test_ai_task_can_call_multiple_readonly_tools_sequentially(
    seeded_session,
    client,
    admin_headers,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "ai-direct-tool-chain",
            "title": "AI Direct Tool Chain",
            "body": "Probe body",
            "status": "draft",
            "visibility": "public",
            "tags": ["probe-tag"],
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="ai_direct_tool_chain_v2",
            name="AI Direct Tool Chain",
            description="Verify the AI can call multiple readonly tools in sequence.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "tools",
                        "type": "tool.query",
                        "label": "Tools",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_keys": ["observe.content.admin_items.get", "observe.content.tags.list"]},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 340, "y": 0},
                        "config": {
                            "instructions": "先读取当前内容，再读取标签列表，最后输出结果。",
                            "tool_usage_mode": "required",
                            "minimum_tool_calls": 2,
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "tool_title": {"type": "string"},
                                    "tool_status": {"type": "string"},
                                    "tag_count": {"type": "integer"},
                                },
                                "required": ["summary", "route", "tool_title", "tool_status", "tag_count"],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-tools-ai",
                        "source": "tools",
                        "target": "ai",
                        "source_handle": "tool",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "tool"},
                    },
                ],
            },
        ),
    )

    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            {"tool_calls": [{"name": "observe.content.admin_items.get", "arguments": {}}]},
            {"tool_calls": [{"name": "observe.content.tags.list", "arguments": {}}]},
            _final_output_tool_call(
                {
                    "summary": "工具链测试完成。",
                    "route": "done",
                    "tool_title": "AI Direct Tool Chain",
                    "tool_status": "draft",
                    "tag_count": 1,
                }
            ),
        ],
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "direct-tool-chain.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                target_type="content",
                target_id=item["id"],
                context_payload={"content_type": "posts", "content_id": item["id"], "item_id": item["id"]},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    tool_results = list(ai_step.output_payload.get("__tool_call_results__") or [])

    assert run.status == "completed"
    assert len(tool_results) == 2
    assert [item["name"] for item in tool_results] == [
        "observe.content.admin_items.get",
        "observe.content.tags.list",
    ]
    assert tool_results[0]["result"]["id"] == item["id"]
    assert tool_results[0]["result"]["title"] == "AI Direct Tool Chain"
    assert isinstance(tool_results[1]["result"]["items"], list)
    assert all("error" not in result for result in tool_results)


def test_ai_task_prefers_native_tool_calls_and_replays_tool_results(
    seeded_session,
    client,
    admin_headers,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "ai-native-tool-chain",
            "title": "AI Native Tool Chain",
            "body": "Native probe body",
            "status": "draft",
            "visibility": "public",
            "tags": ["native-tag"],
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="ai_native_tool_chain_v2",
            name="AI Native Tool Chain",
            description="Verify native tool calls are preferred and tool results are replayed structurally.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "tools",
                        "type": "tool.query",
                        "label": "Tools",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_keys": ["observe.content.admin_items.get"]},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 340, "y": 0},
                        "config": {
                            "instructions": "先读取当前内容，再提交最终输出。",
                            "tool_usage_mode": "required",
                            "minimum_tool_calls": 1,
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "tool_title": {"type": "string"},
                                },
                                "required": ["summary", "route", "tool_title"],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-tools-ai",
                        "source": "tools",
                        "target": "ai",
                        "source_handle": "tool",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "tool"},
                    },
                ],
            },
        ),
    )

    captured_messages: list[list[dict[str, Any]]] = []
    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            _native_tool_call_message(
                {"id": "call_observe", "name": "observe.content.admin_items.get", "arguments": {}}
            ),
            _native_tool_call_message(
                {
                    "id": "call_final",
                    "name": FINAL_OUTPUT_TOOL_NAME,
                    "arguments": {
                        "summary": "原生工具调用完成。",
                        "route": "done",
                        "tool_title": "AI Native Tool Chain",
                    },
                }
            ),
        ],
        captured_messages=captured_messages,
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "native-tool-chain.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                target_type="content",
                target_id=item["id"],
                context_payload={"content_type": "posts", "content_id": item["id"], "item_id": item["id"]},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    tool_results = list(ai_step.output_payload.get("__tool_call_results__") or [])

    assert run.status == "completed"
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "observe.content.admin_items.get"
    assert tool_results[0]["result"]["id"] == item["id"]
    assert any(any(message.get("role") == "tool" for message in batch) for batch in captured_messages)


def test_ai_task_falls_back_to_legacy_json_tool_calls_when_native_tools_are_unsupported(
    seeded_session,
    client,
    admin_headers,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "ai-native-fallback",
            "title": "AI Native Fallback",
            "body": "Fallback body",
            "status": "draft",
            "visibility": "public",
            "tags": ["fallback-tag"],
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="ai_native_tool_fallback_v2",
            name="AI Native Tool Fallback",
            description="Verify native tool calling falls back to legacy JSON tool_calls.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "tools",
                        "type": "tool.query",
                        "label": "Tools",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_keys": ["observe.content.admin_items.get"]},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 340, "y": 0},
                        "config": {
                            "instructions": "读取当前内容后返回最终输出。",
                            "tool_usage_mode": "required",
                            "minimum_tool_calls": 1,
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "tool_title": {"type": "string"},
                                },
                                "required": ["summary", "route", "tool_title"],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-tools-ai",
                        "source": "tools",
                        "target": "ai",
                        "source_handle": "tool",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "tool"},
                    },
                ],
            },
        ),
    )

    request_payloads: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = [
        {"tool_calls": [{"name": "observe.content.admin_items.get", "arguments": {}}]},
        _final_output_tool_call(
            {
                "summary": "已回退到 legacy tool_calls。",
                "route": "done",
                "tool_title": "AI Native Fallback",
            }
        ),
    ]

    class _FallbackFakeResponse:
        def __init__(self, status_code: int = 200, message: dict[str, Any] | None = None, text: str = "") -> None:
            self.status_code = status_code
            self._message = dict(message or {})
            self.text = text
            self.headers = {"content-type": "application/json"}
            self.request = httpx.Request("POST", "https://model.example/v1/chat/completions")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                response = httpx.Response(self.status_code, text=self.text, request=self.request)
                raise httpx.HTTPStatusError("native tools unsupported", request=self.request, response=response)

        def json(self):
            return {"choices": [{"message": self._message}]}

    def fake_post(_url, *args, **kwargs):
        payload = dict(kwargs.get("json") or {})
        request_payloads.append(payload)
        if len(request_payloads) == 1:
            return _FallbackFakeResponse(status_code=400, text='{"error":"Unsupported parameter: tools"}')
        body = responses.pop(0)
        return _FallbackFakeResponse(message={"content": json.dumps(body, ensure_ascii=False)})

    monkeypatch.setattr("aerisun.domain.automation.runtime.httpx.post", fake_post)

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "native-tool-fallback.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                target_type="content",
                target_id=item["id"],
                context_payload={"content_type": "posts", "content_id": item["id"], "item_id": item["id"]},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    tool_results = list(ai_step.output_payload.get("__tool_call_results__") or [])

    assert run.status == "completed"
    assert responses == []
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "observe.content.admin_items.get"
    assert "tools" in request_payloads[0]
    assert "tools" not in request_payloads[1]
    assert request_payloads[1]["response_format"] == {"type": "json_object"}


def test_ai_loop_mode_can_call_tools_step_by_step_across_rounds(
    seeded_session,
    client,
    admin_headers,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "ai-loop-tool-chain",
            "title": "AI Loop Tool Chain",
            "body": "Loop body",
            "status": "draft",
            "visibility": "public",
            "tags": ["loop-tag"],
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="ai_loop_tool_chain_v2",
            name="AI Loop Tool Chain",
            description="Verify loop mode can fetch data in multiple rounds.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "tools",
                        "type": "tool.query",
                        "label": "Tools",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_keys": ["observe.content.admin_items.get", "observe.content.tags.list"]},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 340, "y": 0},
                        "config": {
                            "instructions": "用 loop 模式分两轮查询：第一轮查内容，第二轮查标签。",
                            "mode": "loop",
                            "loop_max_rounds": 3,
                            "tool_usage_mode": "required",
                            "minimum_tool_calls": 1,
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "tool_title": {"type": "string"},
                                    "tag_count": {"type": "integer"},
                                },
                                "required": ["summary", "route", "tool_title", "tag_count"],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-tools-ai",
                        "source": "tools",
                        "target": "ai",
                        "source_handle": "tool",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "tool"},
                    },
                ],
            },
        ),
    )

    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            {"tool_calls": [{"name": "observe.content.admin_items.get", "arguments": {}}]},
            _final_output_tool_call(
                {
                    "continue_loop": True,
                    "note_for_next_round": "需要再查一次标签。",
                    "final_output": {
                        "summary": "第一轮已读到内容。",
                        "route": "looping",
                        "tool_title": "AI Loop Tool Chain",
                        "tag_count": 0,
                    },
                }
            ),
            {"tool_calls": [{"name": "observe.content.tags.list", "arguments": {}}]},
            _final_output_tool_call(
                {
                    "continue_loop": False,
                    "note_for_next_round": "完成。",
                    "final_output": {
                        "summary": "第二轮已读到标签。",
                        "route": "done",
                        "tool_title": "AI Loop Tool Chain",
                        "tag_count": 1,
                    },
                }
            ),
        ],
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "loop-tool-chain.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                target_type="content",
                target_id=item["id"],
                context_payload={"content_type": "posts", "content_id": item["id"], "item_id": item["id"]},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    notebook = list(ai_step.output_payload.get("__loop_notebook__") or [])

    assert run.status == "completed"
    assert ai_step.output_payload["summary"] == "第二轮已读到标签。"
    assert [item["name"] for item in ai_step.output_payload["__tool_call_results__"]] == ["observe.content.tags.list"]
    assert len(notebook) == 2
    assert [item["tool_call_results"][0]["name"] for item in notebook] == [
        "observe.content.admin_items.get",
        "observe.content.tags.list",
    ]
    assert notebook[0]["continue_loop"] is True
    assert notebook[1]["continue_loop"] is False


def test_ai_task_can_invoke_mounted_action_surface(
    seeded_session,
    client,
    admin_headers,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    create_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "ai-mounted-action",
            "title": "AI Mounted Action",
            "body": "Action body",
            "status": "draft",
            "visibility": "public",
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="ai_mounted_action_v2",
            name="AI Mounted Action",
            description="Verify the AI can invoke a mounted action surface.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 340, "y": 0},
                        "config": {
                            "instructions": "调用 mounted action 把标题改成指定值。",
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "final_title": {"type": "string"},
                                },
                                "required": ["summary", "route", "final_title"],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                ],
            },
        ),
    )

    existing_pack = load_workflow_pack(workflow.key)
    write_workflow_pack(
        workflow=workflow,
        query_surfaces=list(existing_pack.query_surfaces),
        action_surfaces=[
            *existing_pack.action_surfaces,
            ActionSurfaceSpec(
                key="safe_update_content",
                label="Safe Update Content",
                description="Update content without approval for controlled tests.",
                base_capability="update_admin_content",
                fixed_args={"content_type": "posts"},
                allowed_args=["item_id", "payload"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                        "payload": {"type": "object"},
                    },
                    "required": ["payload"],
                },
                requires_approval=False,
            ),
        ],
        built_in=existing_pack.manifest.built_in,
    )
    workflow = update_agent_workflow(
        seeded_session,
        workflow_key=workflow.key,
        payload=AgentWorkflowUpdate(
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "action",
                        "type": "apply.action",
                        "label": "Update Action",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_key": "safe_update_content"},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 340, "y": 0},
                        "config": {
                            "instructions": "调用 mounted action 把标题改成指定值。",
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "final_title": {"type": "string"},
                                },
                                "required": ["summary", "route", "final_title"],
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-action-ai",
                        "source": "action",
                        "target": "ai",
                        "source_handle": "action",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "action"},
                    },
                ],
            }
        ),
    )

    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            {
                "tool_calls": [
                    {
                        "name": "safe_update_content",
                        "arguments": {"payload": {"title": "AI Mounted Action Updated"}},
                    }
                ]
            },
            _final_output_tool_call(
                {
                    "summary": "动作执行完成。",
                    "route": "done",
                    "final_title": "AI Mounted Action Updated",
                }
            ),
        ],
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "mounted-action.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                target_type="content",
                target_id=item["id"],
                context_payload={"content_type": "posts", "content_id": item["id"], "item_id": item["id"]},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    action_results = list(ai_step.output_payload.get("__tool_call_results__") or [])

    assert run.status == "completed"
    assert len(action_results) == 1
    assert action_results[0]["name"] == "safe_update_content"
    assert action_results[0]["kind"] == "action"
    assert action_results[0]["result"]["id"] == item["id"]
    assert action_results[0]["result"]["title"] == "AI Mounted Action Updated"

    read_response = client.get(f"/api/v1/admin/posts/{item['id']}", headers=admin_headers)
    assert read_response.status_code == 200
    assert read_response.json()["title"] == "AI Mounted Action Updated"


def test_notification_webhook_observe_builds_formatted_text_without_subscriptions(
    seeded_session,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="webhook_observe_summary_v2",
            name="Webhook Observe Summary",
            description="Webhook observe should always build formatted text.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
            ],
            runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.manual",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "tools",
                        "type": "tool.query",
                        "label": "Tools",
                        "position": {"x": 180, "y": -120},
                        "config": {"surface_keys": ["observe.content.tags.list"]},
                    },
                    {
                        "id": "ai",
                        "type": "ai.task",
                        "label": "AI",
                        "position": {"x": 360, "y": 0},
                        "config": {
                            "instructions": "先读取标签，再返回摘要。",
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "route": {"type": "string"},
                                    "tag_count": {"type": "integer"},
                                },
                                "required": ["summary", "route", "tag_count"],
                            },
                        },
                    },
                    {
                        "id": "webhook",
                        "type": "notification.webhook",
                        "label": "Webhook Observe",
                        "position": {"x": 620, "y": 0},
                        "config": {"linked_subscription_ids": [], "format_requirements": "叙述流程"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-trigger-ai",
                        "source": "trigger",
                        "target": "ai",
                        "source_handle": "next",
                        "target_handle": "mount_1",
                        "type": "default",
                        "config": {},
                    },
                    {
                        "id": "edge-tools-ai",
                        "source": "tools",
                        "target": "ai",
                        "source_handle": "tool",
                        "target_handle": "mount_2",
                        "type": "default",
                        "config": {"kind": "tool"},
                    },
                    {
                        "id": "edge-ai-webhook",
                        "source": "ai",
                        "target": "webhook",
                        "source_handle": "output_1",
                        "target_handle": "in",
                        "type": "default",
                        "config": {},
                    },
                ],
            },
        ),
    )

    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            {"tool_calls": [{"name": "observe.content.tags.list", "arguments": {}}]},
            _final_output_tool_call(
                {
                    "summary": "已读取标签列表并完成分析。",
                    "route": "done",
                    "tag_count": 45,
                }
            ),
        ],
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "webhook-observe-summary.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                context_payload={"probe": "webhook-observe"},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    webhook_step = next(step for step in steps if step.node_key == "webhook")

    assert run.status == "completed"
    assert webhook_step.output_payload["status"] == "completed"
    assert webhook_step.output_payload["delivery_count"] == 0
    assert "摘要：已读取标签列表并完成分析。" in webhook_step.output_payload["formatted_text"]
    assert "调用记录：" in webhook_step.output_payload["formatted_text"]
    assert "observe.content.tags.list" in webhook_step.output_payload["formatted_text"]


def test_notification_webhook_mode_is_stripped_from_graph_config() -> None:
    normalized = compat.normalize_graph_payload(
        {
            "version": 2,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "nodes": [
                {
                    "id": "webhook",
                    "type": "notification.webhook",
                    "label": "Webhook",
                    "position": {"x": 0, "y": 0},
                    "config": {
                        "mode": "observe",
                        "linked_subscription_ids": ["sub-1"],
                        "format_requirements": "summary",
                    },
                }
            ],
            "edges": [],
        }
    )

    node = normalized["nodes"][0]
    assert node["type"] == "notification.webhook"
    assert "mode" not in node["config"]
    assert node["config"]["linked_subscription_ids"] == ["sub-1"]


def test_ai_action_lifecycle_with_webhook_observe_formats_narrative(
    seeded_session,
    tmp_path,
    monkeypatch,
) -> None:
    _set_ready_model_config(seeded_session)

    def _workflow_with_action(
        *,
        key: str,
        action_surface: ActionSurfaceSpec,
        instructions: str,
    ):
        workflow = create_agent_workflow(
            seeded_session,
            AgentWorkflowCreate(
                key=key,
                name=key,
                description=key,
                enabled=True,
                schema_version=2,
                trigger_bindings=[
                    {"id": "manual-trigger", "type": "trigger.manual", "label": "Manual", "enabled": True, "config": {}}
                ],
                runtime_policy={
                    "approval_mode": "risk_based",
                    "allow_high_risk_without_approval": False,
                    "max_steps": 20,
                },
                graph={
                    "version": 2,
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                    "nodes": [
                        {
                            "id": "trigger",
                            "type": "trigger.manual",
                            "label": "Trigger",
                            "position": {"x": 0, "y": 0},
                            "config": {},
                        },
                        {
                            "id": "ai",
                            "type": "ai.task",
                            "label": "AI",
                            "position": {"x": 360, "y": 0},
                            "config": {
                                "instructions": instructions,
                                "output_schema": {
                                    "type": "object",
                                    "properties": {
                                        "summary": {"type": "string"},
                                        "route": {"type": "string"},
                                        "action": {"type": "string"},
                                        "reason": {"type": "string"},
                                        "execution_summary": {"type": "string"},
                                        "execution_result": {"type": "object", "additionalProperties": True},
                                    },
                                    "required": [
                                        "summary",
                                        "route",
                                        "action",
                                        "reason",
                                        "execution_summary",
                                        "execution_result",
                                    ],
                                },
                            },
                        },
                        {
                            "id": "webhook",
                            "type": "notification.webhook",
                            "label": "Webhook Observe",
                            "position": {"x": 620, "y": 0},
                            "config": {"linked_subscription_ids": [], "format_requirements": "叙述执行流程"},
                        },
                    ],
                    "edges": [
                        {
                            "id": "edge-trigger-ai",
                            "source": "trigger",
                            "target": "ai",
                            "source_handle": "next",
                            "target_handle": "mount_1",
                            "type": "default",
                            "config": {},
                        },
                        {
                            "id": "edge-ai-webhook",
                            "source": "ai",
                            "target": "webhook",
                            "source_handle": "output_1",
                            "target_handle": "in",
                            "type": "default",
                            "config": {},
                        },
                    ],
                },
            ),
        )
        pack = load_workflow_pack(workflow.key)
        write_workflow_pack(
            workflow=workflow,
            query_surfaces=list(pack.query_surfaces),
            action_surfaces=[*pack.action_surfaces, action_surface],
            built_in=pack.manifest.built_in,
        )
        workflow = update_agent_workflow(
            seeded_session,
            workflow_key=workflow.key,
            payload=AgentWorkflowUpdate(
                graph={
                    "version": 2,
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                    "nodes": [
                        {
                            "id": "trigger",
                            "type": "trigger.manual",
                            "label": "Trigger",
                            "position": {"x": 0, "y": 0},
                            "config": {},
                        },
                        {
                            "id": "action",
                            "type": "apply.action",
                            "label": "Action",
                            "position": {"x": 180, "y": -120},
                            "config": {"surface_key": action_surface.key},
                        },
                        {
                            "id": "ai",
                            "type": "ai.task",
                            "label": "AI",
                            "position": {"x": 360, "y": 0},
                            "config": {
                                "instructions": instructions,
                                "output_schema": {
                                    "type": "object",
                                    "properties": {
                                        "summary": {"type": "string"},
                                        "route": {"type": "string"},
                                        "action": {"type": "string"},
                                        "reason": {"type": "string"},
                                        "execution_summary": {"type": "string"},
                                        "execution_result": {"type": "object", "additionalProperties": True},
                                    },
                                    "required": [
                                        "summary",
                                        "route",
                                        "action",
                                        "reason",
                                        "execution_summary",
                                        "execution_result",
                                    ],
                                },
                            },
                        },
                        {
                            "id": "webhook",
                            "type": "notification.webhook",
                            "label": "Webhook Observe",
                            "position": {"x": 620, "y": 0},
                            "config": {"linked_subscription_ids": [], "format_requirements": "叙述执行流程"},
                        },
                    ],
                    "edges": [
                        {
                            "id": "edge-trigger-ai",
                            "source": "trigger",
                            "target": "ai",
                            "source_handle": "next",
                            "target_handle": "mount_1",
                            "type": "default",
                            "config": {},
                        },
                        {
                            "id": "edge-action-ai",
                            "source": "action",
                            "target": "ai",
                            "source_handle": "action",
                            "target_handle": "mount_2",
                            "type": "default",
                            "config": {"kind": "action"},
                        },
                        {
                            "id": "edge-ai-webhook",
                            "source": "ai",
                            "target": "webhook",
                            "source_handle": "output_1",
                            "target_handle": "in",
                            "type": "default",
                            "config": {},
                        },
                    ],
                }
            ),
        )
        return workflow

    create_workflow = _workflow_with_action(
        key="ai_action_create_webhook_v2",
        instructions=(
            "Call safe_create_post once. Create a draft post titled 'AI Webhook Lifecycle Created'. "
            "Return the action result unchanged inside execution_result."
        ),
        action_surface=ActionSurfaceSpec(
            key="safe_create_post",
            label="Safe Create Post",
            description="Create post for lifecycle test.",
            base_capability="create_admin_content",
            fixed_args={"content_type": "posts"},
            allowed_args=["payload"],
            input_schema={"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]},
            requires_approval=False,
        ),
    )

    scripted_responses = _mount_runtime_model_sequence(
        monkeypatch,
        [
            {
                "tool_calls": [
                    {
                        "name": "safe_create_post",
                        "arguments": {
                            "payload": {
                                "slug": "ai-webhook-lifecycle-created",
                                "title": "AI Webhook Lifecycle Created",
                                "body": "Created for lifecycle test.",
                                "status": "draft",
                                "visibility": "public",
                            }
                        },
                    }
                ]
            },
            _final_output_tool_call(
                {
                    "summary": "已完成创建动作。",
                    "route": "done",
                    "action": "create",
                    "reason": "lifecycle_test",
                    "execution_summary": "已创建草稿文章。",
                    "execution_result": {
                        "status": "success",
                        "title": "AI Webhook Lifecycle Created",
                    },
                }
            ),
        ],
    )

    runtime = AutomationRuntime(checkpoint_path=tmp_path / "ai-action-webhook-lifecycle.sqlite")
    runtime.start()
    try:
        created = create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=create_workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                trigger_event="manual",
                context_payload={"probe": "ai-action-webhook-lifecycle"},
                input_payload={},
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert scripted_responses == []
    run, steps = get_run_detail(seeded_session, created.run.id)
    ai_step = next(step for step in steps if step.node_key == "ai")
    webhook_step = next(step for step in steps if step.node_key == "webhook")

    tool_calls = list(ai_step.output_payload.get("__tool_call_results__") or [])
    assert run.status == "completed"
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "safe_create_post"
    assert webhook_step.output_payload["status"] == "completed"
    assert webhook_step.output_payload["delivery_count"] == 0
    assert "摘要：已完成创建动作。" in webhook_step.output_payload["formatted_text"]
    assert "执行：已创建草稿文章。" in webhook_step.output_payload["formatted_text"]
    assert "调用记录：" in webhook_step.output_payload["formatted_text"]
    assert "safe_create_post" in webhook_step.output_payload["formatted_text"]

    delete_agent_workflow(seeded_session, workflow_key=create_workflow.key)
    seeded_session.commit()

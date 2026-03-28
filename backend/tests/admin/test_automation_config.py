from __future__ import annotations

import sqlite3

from aerisun.core.settings import get_settings
from aerisun.domain.automation.events import emit_comment_pending, emit_guestbook_pending
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import (
    AgentModelConfigUpdate,
    AgentWorkflowCreate,
    AgentWorkflowUpdate,
    ApprovalDecisionWrite,
    WebhookSubscriptionCreate,
)
from aerisun.domain.automation.service import (
    create_webhook_subscription,
    execute_due_runs,
    list_pending_approvals,
    list_runs,
    list_webhook_deliveries,
    resolve_approval,
)
from aerisun.domain.automation.settings import create_agent_workflow, update_agent_model_config, update_agent_workflow
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
                                '{"summary":"connection_ok","needs_approval":false,'
                                '"proposed_action":"approve"}'
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
                                '{"summary":"connection_ok","needs_approval":false,'
                                '"proposed_action":"approve"}'
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
        headers = {"content-type": "application/json"}

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
        headers = {"content-type": "text/html; charset=utf-8"}

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
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["key"] == "comment_triage_fastlane"
    assert create_response.json()["built_in"] is False

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

    delete_response = client.delete(
        f"{ADMIN_BASE}/workflows/comment_triage_fastlane",
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    final_response = client.get(f"{ADMIN_BASE}/workflows", headers=admin_headers)
    assert final_response.status_code == 200
    final_keys = {item["key"] for item in final_response.json()}
    assert "comment_triage_fastlane" not in final_keys


def test_admin_agent_workflow_draft_conversation_and_create(client, admin_headers, monkeypatch) -> None:
    update_response = client.put(
        f"{ADMIN_BASE}/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key",
            "temperature": 0.2,
            "timeout_seconds": 15,
            "advisory_prompt": "Return strict JSON only.",
        },
    )
    assert update_response.status_code == 200

    responses = iter(
        [
            {
                "assistant_message": "我理解你想做自动评论和留言审核。还有没有必须人工复核的情况？",
                "summary": "用户希望建立一个评论与留言审核工作流。",
                "working_document": (
                    "## Goal\n统一审核评论和留言。\n\n"
                    "## Trigger\n当 comment.pending 或 guestbook.pending 事件到达时进入流程。\n\n"
                    "## Preconditions\n模型配置可用，审核能力已启用。\n\n"
                    "## Decision Matrix\n需要确认是否默认自动通过，以及哪些情况必须人工复核。\n\n"
                    "## Execution Steps\n"
                    "step_id: S1\n"
                    "action: 收集待处理内容\n"
                    "capability_or_endpoint: list_comment_moderation_queue / list_guestbook_moderation_queue\n"
                    "expected_result: 获得可供决策的待审对象\n"
                    "fallback: 如果队列为空则结束本轮\n\n"
                    "## API/Capability Calls\n"
                    "step_id: A1\n"
                    "action: 拉取审核队列\n"
                    "capability_or_endpoint: list_comment_moderation_queue / list_guestbook_moderation_queue\n"
                    "expected_result: 返回待处理评论或留言列表\n"
                    "fallback: 调用失败时记录错误并提示人工检查\n\n"
                    "## Failure Handling\n接口调用失败时进入人工复核。\n\n"
                    "## Final Workflow Shape\n统一审核评论和留言，默认自动通过正常内容。\n"
                ),
                "ready_to_create": False,
                "suggested_template": "community_moderation",
                "questions": [
                    {
                        "key": "review_mode",
                        "prompt": "哪些情况必须人工复核？",
                        "options": [
                            {
                                "label": "全部自动通过",
                                "value": "auto_approve_all_safe",
                                "description": "正常内容直接通过，只保留少量风险词拦截",
                            },
                            {
                                "label": "高风险再人工复核",
                                "value": "manual_review_for_high_risk",
                                "description": "普通内容自动处理，高风险内容进入审批",
                            },
                            {
                                "label": "其他",
                                "value": "other",
                                "description": "自定义审批条件",
                                "requires_input": True,
                            },
                        ],
                    },
                ],
            },
            {
                "assistant_message": "好的，计划已经足够清楚，可以直接创建。",
                "summary": "评论与留言统一进入宽松自动审核流。",
                "working_document": (
                    "## Goal\n评论和留言统一审核。\n\n"
                    "## Trigger\n收到 comment.pending 与 guestbook.pending 时触发。\n\n"
                    "## Preconditions\n工作流启用，审核能力可正常调用。\n\n"
                    "## Decision Matrix\n宽松放行，只拦截辱骂、反党反社会、骚扰和明显垃圾内容。\n\n"
                    "## Execution Steps\n"
                    "step_id: S1\n"
                    "action: 读取待审内容并抽取风险信号。\n"
                    "capability_or_endpoint: list_comment_moderation_queue / list_guestbook_moderation_queue\n"
                    "expected_result: 得到风险判断输入。\n"
                    "fallback: 读取失败则停止自动审核并进入人工处理。\n\n"
                    "step_id: S2\n"
                    "action: 命中拒绝规则时执行拒绝。\n"
                    "capability_or_endpoint: moderate_comment / moderate_guestbook_entry\n"
                    "expected_result: 高风险内容被 reject。\n"
                    "fallback: 写入失败时标记为待人工复核。\n\n"
                    "## API/Capability Calls\n"
                    "step_id: A1\n"
                    "action: 读取评论待审队列\n"
                    "capability_or_endpoint: list_comment_moderation_queue\n"
                    "expected_result: 返回待审评论\n"
                    "fallback: 调用失败时记录日志\n\n"
                    "step_id: A2\n"
                    "action: 执行审核动作\n"
                    "capability_or_endpoint: moderate_comment / moderate_guestbook_entry\n"
                    "expected_result: 内容被 approve 或 reject\n"
                    "fallback: 写入失败则进入人工复核\n\n"
                    "## Failure Handling\n能力调用异常时进入人工复核。\n\n"
                    "## Final Workflow Shape\n宽松自动审核流。"
                ),
                "ready_to_create": True,
                "suggested_template": "community_moderation",
                "questions": [],
            },
            {
                "working_document": (
                    "## Goal\n评论和留言统一审核。\n\n"
                    "## Trigger\n收到 comment.pending 与 guestbook.pending 时触发。\n\n"
                    "## Preconditions\n工作流启用，审核能力可正常调用。\n\n"
                    "## Decision Matrix\n宽松放行，只拦截辱骂、反党反社会、骚扰和明显垃圾内容。\n\n"
                    "## Execution Steps\n"
                    "step_id: S1\n"
                    "action: 读取待审内容并抽取风险信号。\n"
                    "capability_or_endpoint: list_comment_moderation_queue / list_guestbook_moderation_queue\n"
                    "expected_result: 得到风险判断输入。\n"
                    "fallback: 读取失败则停止自动审核并进入人工处理。\n\n"
                    "step_id: S2\n"
                    "action: 命中拒绝规则时执行拒绝。\n"
                    "capability_or_endpoint: moderate_comment / moderate_guestbook_entry\n"
                    "expected_result: 高风险内容被 reject。\n"
                    "fallback: 写入失败时标记为待人工复核。\n\n"
                    "## API/Capability Calls\n"
                    "step_id: A1\n"
                    "action: 读取评论待审队列\n"
                    "capability_or_endpoint: list_comment_moderation_queue\n"
                    "expected_result: 返回待审评论\n"
                    "fallback: 调用失败时记录日志\n\n"
                    "step_id: A2\n"
                    "action: 执行审核动作\n"
                    "capability_or_endpoint: moderate_comment / moderate_guestbook_entry\n"
                    "expected_result: 内容被 approve 或 reject\n"
                    "fallback: 写入失败则进入人工复核\n\n"
                    "## Failure Handling\n能力调用异常时进入人工复核。\n\n"
                    "## Final Workflow Shape\n宽松自动审核流。"
                ),
            },
            {
                "summary": "已根据对话创建评论与留言审核工作流。",
                "analysis": "需求已经收敛到一个共享的宽松审核流。",
                "template_key": "community_moderation",
                "used_capabilities": ["moderate_comment", "moderate_guestbook_entry"],
                "workflow": {
                    "key": "community_moderation_v1",
                    "name": "评论与留言自动审核",
                    "description": "评论和留言统一自动审核。",
                    "enabled": True,
                    "require_human_approval": False,
                    "instructions": "默认自动通过正常内容，只拒绝辱骂、反党反社会、骚扰和明显垃圾内容。",
                },
            },
        ]
    )

    monkeypatch.setattr("aerisun.domain.automation.service.invoke_model_json", lambda *args, **kwargs: next(responses))

    first = client.post(
        f"{ADMIN_BASE}/workflow-draft/messages",
        headers=admin_headers,
        json={"message": "我想做一个评论和留言的自动审核工作流。"},
    )
    assert first.status_code == 200
    assert first.json()["ready_to_create"] is False
    assert len(first.json()["questions"]) == 1
    assert first.json()["questions"][0]["key"] == "review_mode"
    assert "step_id:" in first.json()["working_document"]

    draft = client.get(f"{ADMIN_BASE}/workflow-draft", headers=admin_headers)
    assert draft.status_code == 200
    assert draft.json()["summary"] == "用户希望建立一个评论与留言审核工作流。"

    second = client.post(
        f"{ADMIN_BASE}/workflow-draft/messages",
        headers=admin_headers,
        json={"message": "默认自动通过，只有辱骂、反党反社会、骚扰和明显垃圾内容才拦截。"},
    )
    assert second.status_code == 200
    assert second.json()["ready_to_create"] is False
    assert second.json()["status"] == "finalizing_plan"
    assert second.json()["questions"] == []

    created = client.post(
        f"{ADMIN_BASE}/workflow-draft/create",
        headers=admin_headers,
        json={"force": True},
    )
    assert created.status_code == 200
    assert created.json()["workflow"]["key"] == "community_moderation_v1"
    assert created.json()["workflow"]["require_human_approval"] is False

    cleared = client.get(f"{ADMIN_BASE}/workflow-draft", headers=admin_headers)
    assert cleared.status_code == 200
    assert cleared.json() is None


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
                                '{"summary":"LLM review summary","needs_approval":true,'
                                '"proposed_action":"reject"}'
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
                            "content": (
                                '{"summary":"Looks risky","needs_approval":false,'
                                '"proposed_action":"reject"}'
                            )
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
                                '{"summary":"Looks safe to approve","needs_approval":true,'
                                '"proposed_action":"approve"}'
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
        item.event_type == "comment.approve"
        and item.payload.get("payload", {}).get("comment_id") == str(comment_id)
        for item in deliveries
    )

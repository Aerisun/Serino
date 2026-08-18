from __future__ import annotations

from aerisun.domain.agent.mcp_admin_tools import get_admin_content_by_url
from aerisun.domain.automation.catalog import build_workflow_catalog
from aerisun.domain.automation.compat import normalize_graph_payload
from aerisun.domain.automation.compiler import derive_ai_output_schema
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import (
    AgentWorkflowCreate,
    AgentWorkflowMessageRunCreateWrite,
)
from aerisun.domain.automation.service import (
    create_message_workflow_run,
    get_agent_message,
    list_agent_messages,
)
from aerisun.domain.automation.settings import create_agent_workflow
from aerisun.domain.automation.validation import compile_workflow
from aerisun.domain.content.models import DiaryEntry

ADMIN_BASE = "/api/v1/admin/automation"


def _node(node_id: str, node_type: str, x: int) -> dict[str, object]:
    return {
        "id": node_id,
        "type": node_type,
        "label": node_type,
        "position": {"x": x, "y": 0},
        "config": {},
    }


def test_catalog_exposes_internal_message_trigger_and_output(seeded_session) -> None:
    catalog = build_workflow_catalog(seeded_session)
    definitions = {item.type: item for item in catalog.node_types}
    trigger_types = {item.type: item for item in catalog.trigger_types}

    message_trigger = definitions["trigger.message"]
    message_output = definitions["output.message"]

    assert message_trigger.label == "留言触发"
    assert trigger_types["trigger.message"].label == "留言触发"
    assert message_trigger.default_config["event_type"] == "message.submitted"
    assert message_output.label == "留言"
    assert message_output.input_ports[0].id == "message"
    assert message_output.output_ports == []
    assert any(item.key == "get_admin_content_by_url" for item in catalog.readonly_tools)


def test_content_url_reader_returns_full_admin_content(seeded_session) -> None:
    diary = seeded_session.query(DiaryEntry).first()
    assert diary is not None
    diary.visibility = "private"
    seeded_session.flush()

    result = get_admin_content_by_url(
        seeded_session,
        url=f"https://example.com/diary/{diary.slug}?preview=true#content",
    )

    assert result["content_type"] == "diary"
    assert result["slug"] == diary.slug
    assert result["item"]["id"] == diary.id
    assert result["item"]["body"] == diary.body
    assert result["item"]["visibility"] == "private"


def test_workflow_rejects_more_than_one_trigger_node(seeded_session) -> None:
    result = compile_workflow(
        {
            "key": "multiple_triggers",
            "name": "Multiple triggers",
            "trigger_bindings": [
                {
                    "id": "manual",
                    "type": "trigger.manual",
                    "label": "Manual",
                    "enabled": True,
                    "config": {},
                },
                {
                    "id": "message",
                    "type": "trigger.message",
                    "label": "Message",
                    "enabled": True,
                    "config": {"event_type": "message.submitted"},
                },
            ],
            "graph": {
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    _node("manual", "trigger.manual", 0),
                    _node("message", "trigger.message", 240),
                ],
                "edges": [],
            },
        },
        session=seeded_session,
    )

    assert any(issue.code == "graph.multiple_triggers" for issue in result.issues)


def test_workflow_rejects_more_than_one_trigger_binding(seeded_session) -> None:
    result = compile_workflow(
        {
            "key": "multiple_trigger_bindings",
            "name": "Multiple bindings",
            "trigger_bindings": [
                {
                    "id": "message-primary",
                    "type": "trigger.message",
                    "label": "Message",
                    "enabled": True,
                    "config": {"event_type": "message.submitted"},
                },
                {
                    "id": "message-secondary",
                    "type": "trigger.message",
                    "label": "Message 2",
                    "enabled": True,
                    "config": {"event_type": "message.submitted"},
                },
            ],
            "graph": {
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [_node("message", "trigger.message", 0)],
                "edges": [],
            },
        },
        session=seeded_session,
    )

    assert any(issue.code == "workflow.multiple_trigger_bindings" for issue in result.issues)


def test_ai_task_derives_message_output_contract(seeded_session) -> None:
    catalog = build_workflow_catalog(seeded_session)
    node_types = {item.type: item for item in catalog.node_types}
    graph_nodes = [
        _node("ai", "ai.task", 0),
        _node("message", "output.message", 320),
    ]
    graph_edges = [
        {
            "id": "ai-to-message",
            "source": "ai",
            "target": "message",
            "source_handle": "result",
            "target_handle": "message",
            "type": "default",
            "config": {"kind": "data"},
        }
    ]

    schema, source_node_ids = derive_ai_output_schema(
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        ai_node_id="ai",
        operation_catalog=catalog.operation_catalog,
        node_type_registry=node_types,
    )

    assert schema["properties"]["message"]["type"] == "string"
    assert schema["required"] == ["message"]
    assert source_node_ids == ["message"]


def test_modern_ai_task_does_not_receive_legacy_output_contract() -> None:
    normalized = normalize_graph_payload(
        {
            "version": 2,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "nodes": [
                {
                    **_node("ai", "ai.task", 0),
                    "config": {
                        "instructions": "Read the mounted content and write a literary review.",
                        "mode": "direct",
                        "tool_usage_mode": "required",
                    },
                },
                _node("message", "output.message", 320),
            ],
            "edges": [
                {
                    "id": "ai-to-message",
                    "source": "ai",
                    "target": "message",
                    "source_handle": "result",
                    "target_handle": "message",
                    "type": "default",
                    "config": {"kind": "data"},
                }
            ],
        }
    )

    ai_config = normalized["nodes"][0]["config"]
    assert "output_schema" not in ai_config
    assert "output_contract" not in ai_config
    assert "input_mode" not in ai_config
    assert "output_mode" not in ai_config


def test_legacy_ai_task_alias_still_receives_migrated_contracts() -> None:
    normalized = normalize_graph_payload(
        {
            "version": 1,
            "nodes": [
                {
                    **_node("ai", "ai_task", 0),
                    "config": {"instructions": "Review the content."},
                }
            ],
            "edges": [],
        }
    )

    ai_node = normalized["nodes"][0]
    assert ai_node["type"] == "ai.task"
    assert ai_node["config"]["input_contract"]["fields"][0]["key"] == "context"
    assert ai_node["config"]["output_contract"]["output_schema"]["properties"]["summary"] == {"type": "string"}


def test_message_run_persists_internal_message_and_lists_it(seeded_session, tmp_path) -> None:
    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="message_projection",
            name="Message projection",
            enabled=True,
            trigger_bindings=[
                {
                    "id": "message-trigger",
                    "type": "trigger.message",
                    "label": "留言触发",
                    "enabled": True,
                    "config": {"event_type": "message.submitted", "target_type": "message"},
                }
            ],
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    _node("trigger", "trigger.message", 0),
                    {
                        **_node("output", "output.message", 320),
                        "config": {"message_path": "message"},
                    },
                ],
                "edges": [
                    {
                        "id": "trigger-to-output",
                        "source": "trigger",
                        "target": "output",
                        "source_handle": "next",
                        "target_handle": "message",
                        "type": "default",
                        "config": {"kind": "data"},
                    }
                ],
            },
        ),
    )
    runtime = AutomationRuntime(checkpoint_path=tmp_path / "message-runtime.sqlite")
    runtime.start()
    try:
        message = "## 《傍晚电车与橙色天光》文学赏析\n\n请重点分析叙事节奏。"
        created = create_message_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowMessageRunCreateWrite(
                message=message,
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert created.run.status == "completed"
    assert created.run.trigger_kind == "message"
    assert created.run.context_payload["message"] == message
    message_step = next(step for step in created.steps if step.node_key == "output")
    assert message_step.step_kind == "message_output"
    assert message_step.output_payload["message"].endswith("请重点分析叙事节奏。")

    collection = list_agent_messages(seeded_session, limit=25)
    assert collection.total == 1
    assert collection.items[0].run_id == created.run.id
    assert collection.items[0].workflow_key == workflow.key
    assert collection.items[0].message_preview == "《傍晚电车与橙色天光》文学赏析"
    assert not hasattr(collection.items[0], "message")

    detail = get_agent_message(seeded_session, message_id=message_step.id)
    assert detail.message == message_step.output_payload["message"]


def test_admin_message_trigger_and_activity_endpoints(client, admin_headers) -> None:
    workflow_payload = {
        "key": "message_endpoint",
        "name": "Message endpoint",
        "enabled": True,
        "trigger_bindings": [
            {
                "id": "message-trigger",
                "type": "trigger.message",
                "label": "留言触发",
                "enabled": True,
                "config": {"event_type": "message.submitted", "target_type": "message"},
            }
        ],
        "graph": {
            "version": 2,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "nodes": [
                _node("trigger", "trigger.message", 0),
                {
                    **_node("output", "output.message", 320),
                    "config": {"message_path": "message"},
                },
            ],
            "edges": [
                {
                    "id": "trigger-to-output",
                    "source": "trigger",
                    "target": "output",
                    "source_handle": "next",
                    "target_handle": "message",
                    "type": "default",
                    "config": {"kind": "data"},
                }
            ],
        },
    }
    create_response = client.post(
        f"{ADMIN_BASE}/workflows",
        headers=admin_headers,
        json=workflow_payload,
    )
    assert create_response.status_code == 201

    message = "## 《测试作品》文学赏析\n\n请分析语言和结构。"
    run_response = client.post(
        f"{ADMIN_BASE}/workflows/message_endpoint/message-runs",
        headers=admin_headers,
        json={"message": message, "execute_immediately": True},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["run"]["trigger_kind"] == "message"
    assert run_payload["run"]["status"] == "completed"

    messages_response = client.get(
        f"{ADMIN_BASE}/messages",
        headers=admin_headers,
        params={"workflow_key": "message_endpoint"},
    )
    assert messages_response.status_code == 200
    messages_payload = messages_response.json()
    assert messages_payload["total"] == 1
    assert messages_payload["items"][0]["message_preview"] == "《测试作品》文学赏析"
    assert "message" not in messages_payload["items"][0]
    assert messages_payload["items"][0]["run_id"] == run_payload["run"]["id"]

    detail_response = client.get(
        f"{ADMIN_BASE}/messages/{messages_payload['items'][0]['id']}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["message"] == message

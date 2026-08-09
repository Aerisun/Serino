from __future__ import annotations

import sqlite3

from aerisun.core.settings import get_settings
from aerisun.domain.automation import runtime as runtime_module
from aerisun.domain.automation.packs import load_workflow_pack, write_workflow_pack
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import (
    ActionSurfaceSpec,
    AgentWorkflowCreate,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowUpdate,
    WebhookSubscriptionCreate,
)
from aerisun.domain.automation.service import (
    create_webhook_subscription,
    get_run_detail,
    list_webhook_deliveries,
)
from aerisun.domain.automation.service import (
    test_workflow_run as run_workflow_test,
)
from aerisun.domain.automation.settings import create_agent_workflow, update_agent_workflow
from aerisun.domain.waline.service import connect_waline_db


def _graph(*nodes: dict, edges: list[dict]) -> dict:
    return {
        "version": 2,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "nodes": list(nodes),
        "edges": edges,
    }


def _trigger_node() -> dict:
    return {
        "id": "trigger",
        "type": "trigger.manual",
        "label": "Manual",
        "position": {"x": 0, "y": 0},
        "config": {},
    }


def _edge(target: str) -> dict:
    return {
        "id": f"edge-trigger-{target}",
        "source": "trigger",
        "target": target,
        "type": "default",
        "config": {},
    }


def _create_workflow(seeded_session, *, key: str, terminal_node: dict, runtime_policy: dict | None = None):
    return create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key=key,
            name=key,
            description="Dry-run behavior fixture.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[
                {
                    "id": "manual-trigger",
                    "type": "trigger.manual",
                    "label": "Manual",
                    "enabled": True,
                    "config": {},
                }
            ],
            runtime_policy=runtime_policy
            or {
                "approval_mode": "risk_based",
                "allow_high_risk_without_approval": False,
                "max_steps": 20,
            },
            graph=_graph(_trigger_node(), terminal_node, edges=[_edge(str(terminal_node["id"]))]),
        ),
    )


def _run_test(seeded_session, tmp_path, *, workflow_key: str, target_type: str | None = None, target_id=None):
    runtime = AutomationRuntime(checkpoint_path=tmp_path / f"{workflow_key}.sqlite")
    runtime.start()
    try:
        return run_workflow_test(
            seeded_session,
            runtime,
            workflow_key=workflow_key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                target_type=target_type,
                target_id=None if target_id is None else str(target_id),
                execution_mode="live",
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()


def _seed_waiting_comment(connection: sqlite3.Connection) -> int:
    cursor = connection.execute(
        """
        INSERT INTO wl_comment (
            user_id, comment, insertedAt, ip, link, mail, nick, pid, rid,
            sticky, status, "like", ua, url, createdAt, updatedAt
        ) VALUES (
            NULL, 'Dry-run moderation target', '2026-08-09 09:00:00', '', NULL, NULL,
            'Dry Run', NULL, NULL, NULL, 'waiting', 0, '', '/posts/dry-run',
            '2026-08-09 09:00:00', '2026-08-09 09:00:00'
        )
        """
    )
    connection.commit()
    return int(cursor.lastrowid)


def test_test_run_forces_dry_run_and_does_not_moderate_comment(seeded_session, tmp_path) -> None:
    workflow = _create_workflow(
        seeded_session,
        key="dry_run_comment_moderation",
        terminal_node={
            "id": "moderate",
            "type": "operation.capability",
            "label": "Moderate",
            "position": {"x": 240, "y": 0},
            "config": {
                "operation_key": "moderate_comment",
                "action": "approve",
                "reason": "dry_run_test",
            },
        },
        runtime_policy={
            "approval_mode": "risk_based",
            "allow_high_risk_without_approval": True,
            "max_steps": 20,
        },
    )
    settings = get_settings()
    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waiting_comment(connection)

    created = _run_test(
        seeded_session,
        tmp_path,
        workflow_key=workflow.key,
        target_type="comment",
        target_id=comment_id,
    )

    assert created.run.status == "completed"
    assert created.run.execution_mode == "dry_run"
    assert created.run.result_payload["simulated"] is True
    assert created.run.result_payload["applied"] is False
    assert created.run.result_payload["execution"]["capability"] == "moderate_comment"
    with connect_waline_db(settings.waline_db_path) as connection:
        row = connection.execute("SELECT status FROM wl_comment WHERE id = ?", (comment_id,)).fetchone()
        assert row is not None
        assert row["status"] == "waiting"


def test_dry_run_validates_action_surface_without_calling_handler(
    seeded_session,
    tmp_path,
    monkeypatch,
) -> None:
    workflow = _create_workflow(
        seeded_session,
        key="dry_run_action_surface",
        terminal_node={
            "id": "placeholder",
            "type": "note",
            "label": "Placeholder",
            "position": {"x": 240, "y": 0},
            "config": {"content": "placeholder"},
        },
    )
    pack = load_workflow_pack(workflow.key)
    write_workflow_pack(
        workflow=workflow,
        query_surfaces=list(pack.query_surfaces),
        action_surfaces=[
            *pack.action_surfaces,
            ActionSurfaceSpec(
                key="dry_run_noop_action",
                label="Dry-run noop action",
                description="Must be validated without execution.",
                base_capability="noop",
                requires_approval=False,
            ),
        ],
        built_in=pack.manifest.built_in,
    )
    workflow = update_agent_workflow(
        seeded_session,
        workflow_key=workflow.key,
        payload=AgentWorkflowUpdate(
            graph=_graph(
                _trigger_node(),
                {
                    "id": "action",
                    "type": "apply.action",
                    "label": "Action",
                    "position": {"x": 240, "y": 0},
                    "config": {"surface_key": "dry_run_noop_action"},
                },
                edges=[_edge("action")],
            )
        ),
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("dry-run must not call the action surface handler")

    monkeypatch.setattr(runtime_module, "execute_action_surface", fail_if_called)

    created = _run_test(seeded_session, tmp_path, workflow_key=workflow.key)
    _run, steps = get_run_detail(seeded_session, created.run.id)
    action_step = next(step for step in steps if step.node_key == "action")

    assert created.run.status == "completed"
    assert created.run.result_payload["simulated"] is True
    assert action_step.output_payload["simulated"] is True
    assert action_step.output_payload["execution"]["surface_key"] == "dry_run_noop_action"


def test_dry_run_notification_does_not_create_webhook_delivery(seeded_session, tmp_path) -> None:
    subscription = create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="dry-run-destination",
            target_url="https://example.com/dry-run",
            event_types=["dry.run.notification"],
            status="active",
        ),
    )
    workflow = _create_workflow(
        seeded_session,
        key="dry_run_webhook_notification",
        terminal_node={
            "id": "webhook",
            "type": "notification.webhook",
            "label": "Webhook",
            "position": {"x": 240, "y": 0},
            "config": {
                "event_type": "dry.run.notification",
                "linked_subscription_ids": [subscription.id],
            },
        },
    )

    assert list_webhook_deliveries(seeded_session) == []
    created = _run_test(seeded_session, tmp_path, workflow_key=workflow.key)
    assert list_webhook_deliveries(seeded_session) == []

    _run, steps = get_run_detail(seeded_session, created.run.id)
    webhook_step = next(step for step in steps if step.node_key == "webhook")
    assert created.run.status == "completed"
    assert webhook_step.output_payload["simulated"] is True
    assert webhook_step.output_payload["simulated_delivery_count"] == 1
    assert webhook_step.output_payload["delivery_count"] == 0

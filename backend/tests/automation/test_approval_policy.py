from __future__ import annotations

from itertools import pairwise

import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError

from aerisun.domain.automation import repository, runs
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import (
    AgentWorkflowCreate,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowRuntimePolicy,
    ApprovalDecisionWrite,
)
from aerisun.domain.automation.service import list_pending_approvals, resolve_approval
from aerisun.domain.automation.settings import create_agent_workflow
from aerisun.domain.automation.validation import compile_workflow
from aerisun.domain.exceptions import StateConflict, ValidationError


def _edge(source: str, target: str) -> dict:
    return {
        "id": f"edge-{source}-{target}",
        "source": source,
        "target": target,
        "type": "default",
        "config": {},
    }


def test_retry_policy_is_normalized_at_workflow_boundary() -> None:
    policy = AgentWorkflowRuntimePolicy.model_validate({"retry_policy": {"max_attempts": 5}})

    assert policy.retry_policy.model_dump(mode="json") == {
        "max_attempts": 5,
        "initial_seconds": 5.0,
        "multiplier": 2.0,
        "max_seconds": 300.0,
        "jitter_ratio": 0.1,
    }

    with pytest.raises(PydanticValidationError):
        AgentWorkflowRuntimePolicy.model_validate({"retry_policy": {"jitter_ratio": 0.9}})


def _create_approval_workflow(seeded_session, *, key: str, approval_count: int):
    nodes: list[dict] = [
        {
            "id": "trigger",
            "type": "trigger.manual",
            "label": "Trigger",
            "position": {"x": 0, "y": 0},
            "config": {},
        }
    ]
    edges: list[dict] = []
    previous = "trigger"
    for index in range(approval_count):
        node_id = f"approval-{index + 1}"
        nodes.append(
            {
                "id": node_id,
                "type": "approval.review",
                "label": f"Approval {index + 1}",
                "position": {"x": 240 * (index + 1), "y": 0},
                "config": {"mode": "always", "approval_type": "manual_review"},
            }
        )
        edge = _edge(previous, node_id)
        if previous.startswith("approval-"):
            edge["config"] = {"kind": "data"}
        edges.append(edge)
        previous = node_id
    nodes.append(
        {
            "id": "done",
            "type": "note",
            "label": "Done",
            "position": {"x": 240 * (approval_count + 1), "y": 0},
            "config": {"content": "done"},
        }
    )
    final_edge = _edge(previous, "done")
    if previous.startswith("approval-"):
        final_edge["config"] = {"kind": "data"}
    edges.append(final_edge)
    return create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key=key,
            name=key,
            description="Approval policy fixture.",
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
            runtime_policy={"max_steps": 20},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": nodes,
                "edges": edges,
            },
        ),
    )


def _create_run(seeded_session, runtime, *, workflow_key: str):
    return runs.create_workflow_run(
        seeded_session,
        runtime,
        workflow_key=workflow_key,
        payload=AgentWorkflowRunCreateWrite(
            trigger_binding_id="manual-trigger",
            execute_immediately=True,
        ),
    )


def test_approval_can_only_be_consumed_once(seeded_session, tmp_path, admin_user) -> None:
    workflow = _create_approval_workflow(
        seeded_session,
        key="single_consume_approval_workflow",
        approval_count=1,
    )
    runtime = AutomationRuntime(checkpoint_path=tmp_path / "single-approval.sqlite")
    runtime.start()
    try:
        created = _create_run(seeded_session, runtime, workflow_key=workflow.key)
        approval = list_pending_approvals(seeded_session)[0]
        resolved = resolve_approval(
            seeded_session,
            runtime,
            approval_id=approval.id,
            actor_id=admin_user.id,
            decision_payload=ApprovalDecisionWrite(action="approve", reason="first"),
        )
        assert created.run.status == "awaiting_approval"
        assert resolved.status == "completed"

        with pytest.raises(StateConflict):
            resolve_approval(
                seeded_session,
                runtime,
                approval_id=approval.id,
                actor_id=admin_user.id,
                decision_payload=ApprovalDecisionWrite(action="approve", reason="duplicate"),
            )
    finally:
        runtime.stop()


def test_approval_resume_reduces_a_second_interrupt_instead_of_completing(
    seeded_session,
    tmp_path,
    admin_user,
) -> None:
    workflow = _create_approval_workflow(
        seeded_session,
        key="two_stage_approval_workflow",
        approval_count=2,
    )
    runtime = AutomationRuntime(checkpoint_path=tmp_path / "two-approvals.sqlite")
    runtime.start()
    try:
        created = _create_run(seeded_session, runtime, workflow_key=workflow.key)
        first = list_pending_approvals(seeded_session)[0]

        after_first = resolve_approval(
            seeded_session,
            runtime,
            approval_id=first.id,
            actor_id=admin_user.id,
            decision_payload=ApprovalDecisionWrite(action="approve", reason="stage_one"),
        )
        pending = list_pending_approvals(seeded_session)

        assert created.run.status == "awaiting_approval"
        assert after_first.status == "awaiting_approval"
        assert len(pending) == 1
        assert pending[0].node_key == "approval-2"

        completed = resolve_approval(
            seeded_session,
            runtime,
            approval_id=pending[0].id,
            actor_id=admin_user.id,
            decision_payload=ApprovalDecisionWrite(action="approve", reason="stage_two"),
        )
        assert completed.status == "completed"
    finally:
        runtime.stop()


def test_runtime_policy_max_steps_is_applied_to_langgraph(seeded_session, tmp_path) -> None:
    nodes = [
        {
            "id": "trigger",
            "type": "trigger.manual",
            "label": "Trigger",
            "position": {"x": 0, "y": 0},
            "config": {},
        },
        *[
            {
                "id": f"note-{index}",
                "type": "note",
                "label": f"Note {index}",
                "position": {"x": 200 * index, "y": 0},
                "config": {"content": str(index)},
            }
            for index in range(1, 6)
        ],
    ]
    node_ids = [str(node["id"]) for node in nodes]
    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="max_steps_workflow",
            name="Max steps workflow",
            description="Max steps must reach LangGraph.",
            enabled=True,
            schema_version=2,
            trigger_bindings=[{"id": "manual-trigger", "type": "trigger.manual"}],
            runtime_policy={"max_steps": 2},
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": nodes,
                "edges": [_edge(source, target) for source, target in pairwise(node_ids)],
            },
        ),
    )
    runtime = AutomationRuntime(checkpoint_path=tmp_path / "max-steps.sqlite")
    runtime.start()
    try:
        created = _create_run(seeded_session, runtime, workflow_key=workflow.key)
    finally:
        runtime.stop()

    assert created.run.status == "failed"
    assert created.run.error_code == "GraphRecursionError"


def _create_retry_workflow(seeded_session, *, key: str):
    return create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key=key,
            name=key,
            description="Retry policy fixture.",
            trigger_bindings=[{"id": "manual-trigger", "type": "trigger.manual"}],
            runtime_policy={
                "max_steps": 20,
                "retry_policy": {
                    "max_attempts": 3,
                    "initial_seconds": 0,
                    "multiplier": 2,
                    "max_seconds": 30,
                    "jitter_ratio": 0,
                },
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
                        "id": "note",
                        "type": "note",
                        "label": "Note",
                        "position": {"x": 200, "y": 0},
                        "config": {"content": "retry"},
                    },
                ],
                "edges": [_edge("trigger", "note")],
            },
        ),
    )


def test_retryable_runtime_error_is_scheduled_with_bounded_policy(seeded_session) -> None:
    workflow = _create_retry_workflow(seeded_session, key="transient_retry_workflow")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )

    class TimeoutRuntime:
        def invoke(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("model timed out")

    assert (
        runs.execute_due_runs(
            seeded_session,
            TimeoutRuntime(),
            worker_id="retry-worker",
        )
        == 1
    )
    seeded_session.expire_all()
    persisted = repository.get_agent_run(seeded_session, queued.id)
    assert persisted is not None
    assert persisted.status == "queued"
    assert persisted.attempt_count == 1
    assert persisted.available_at is not None
    assert persisted.error_code == "ReadTimeout"
    assert any(
        step.step_kind == "run_retry_scheduled"
        for step in repository.list_agent_run_steps(seeded_session, run_id=queued.id)
    )


def test_validation_error_is_not_automatically_retried(seeded_session) -> None:
    workflow = _create_retry_workflow(seeded_session, key="non_retryable_workflow")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )

    class InvalidRuntime:
        def invoke(self, *_args, **_kwargs):
            raise ValidationError("invalid workflow input")

    assert (
        runs.execute_due_runs(
            seeded_session,
            InvalidRuntime(),
            worker_id="non-retry-worker",
        )
        == 1
    )
    seeded_session.expire_all()
    persisted = repository.get_agent_run(seeded_session, queued.id)
    assert persisted is not None
    assert persisted.status == "failed"
    assert persisted.attempt_count == 1


def test_operation_risk_cannot_be_downgraded_by_node_config(
    seeded_session,
    tmp_path,
    monkeypatch,
) -> None:
    workflow = create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key="risk_floor_workflow",
            name="Risk floor workflow",
            description="Capability risk is an immutable floor.",
            trigger_bindings=[{"id": "manual-trigger", "type": "trigger.manual"}],
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
                        "id": "update",
                        "type": "operation.capability",
                        "label": "Update",
                        "position": {"x": 200, "y": 0},
                        "config": {
                            "operation_key": "update_admin_content",
                            "risk_level": "low",
                            "argument_mappings": [
                                {"name": "content_type", "source": "literal", "value": "posts"},
                                {
                                    "name": "payload",
                                    "source": "literal",
                                    "value": {"visibility": "private"},
                                },
                            ],
                        },
                    },
                ],
                "edges": [_edge("trigger", "update")],
            },
        ),
    )
    validation = compile_workflow(workflow.model_dump(mode="json"), session=seeded_session)
    issue_codes = {item.code for item in validation.issues}
    assert "workflow.risk_downgrade_ignored" in issue_codes
    assert "workflow.high_risk_without_approval" in issue_codes

    def fail_if_executed(*_args, **_kwargs):
        raise AssertionError("high-risk capability must be stopped before execution")

    monkeypatch.setattr("aerisun.domain.automation.runtime.execute_operation", fail_if_executed)
    runtime = AutomationRuntime(checkpoint_path=tmp_path / "risk-floor.sqlite")
    runtime.start()
    try:
        created = runs.create_workflow_run(
            seeded_session,
            runtime,
            workflow_key=workflow.key,
            payload=AgentWorkflowRunCreateWrite(
                trigger_binding_id="manual-trigger",
                target_type="content",
                target_id="content-1",
                execute_immediately=True,
            ),
        )
    finally:
        runtime.stop()

    assert created.run.status == "failed"
    assert created.run.error_code == "ValidationError"
    assert "requires approval" in str(created.run.error_message)

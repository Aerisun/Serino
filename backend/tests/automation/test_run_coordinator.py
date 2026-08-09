from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import get_args
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from aerisun.core.db import get_session_factory
from aerisun.core.time import shanghai_now
from aerisun.domain.automation import repository, runs
from aerisun.domain.automation import runtime as runtime_module
from aerisun.domain.automation.models import AgentRun, AutomationEvent, AutomationStatus
from aerisun.domain.automation.runtime_registry import get_automation_runtime
from aerisun.domain.automation.schemas import (
    AgentWorkflowCreate,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowUpdate,
)
from aerisun.domain.automation.settings import create_agent_workflow, update_agent_workflow
from aerisun.domain.exceptions import StateConflict


def _create_workflow(seeded_session, *, key: str = "coordinator_noop", name: str = "Original workflow"):
    return create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key=key,
            name=name,
            description="Coordinator reliability fixture.",
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
                    }
                ],
            },
        ),
    )


def _create_run(
    seeded_session,
    *,
    workflow_key: str = "coordinator_noop",
    status: str = "queued",
    available_at=None,
) -> AgentRun:
    run = AgentRun(
        workflow_key=workflow_key,
        status=status,
        trigger_kind="manual",
        thread_id=uuid4().hex,
        available_at=available_at or shanghai_now(),
    )
    seeded_session.add(run)
    seeded_session.commit()
    seeded_session.refresh(run)
    return run


def _snapshot_fingerprint(snapshot: dict[str, object]) -> str:
    serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _note_graph(*, first_content: str = "original", trigger_type: str = "trigger.manual") -> dict[str, object]:
    return {
        "version": 2,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "nodes": [
            {
                "id": "trigger",
                "type": trigger_type,
                "label": "Trigger",
                "position": {"x": 0, "y": 0},
                "config": {},
            },
            {
                "id": "first-note",
                "type": "note",
                "label": "First note",
                "position": {"x": 240, "y": 0},
                "config": {"content": first_content},
            },
            {
                "id": "second-note",
                "type": "note",
                "label": "Second note",
                "position": {"x": 480, "y": 0},
                "config": {"content": "second"},
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source": "trigger",
                "target": "first-note",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-2",
                "source": "first-note",
                "target": "second-note",
                "label": "",
                "type": "default",
                "config": {},
            },
        ],
    }


def _create_note_workflow(
    seeded_session,
    *,
    key: str,
    first_content: str = "original",
    webhook: bool = False,
):
    trigger_type = "trigger.webhook" if webhook else "trigger.manual"
    binding = {
        "id": "incoming-hook" if webhook else "manual-trigger",
        "type": trigger_type,
        "label": "Trigger",
        "enabled": True,
        "config": {"secret": "test-secret-123456"} if webhook else {},
    }
    return create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key=key,
            name=key,
            description="Coordinator node-boundary fixture.",
            trigger_bindings=[binding],
            graph=_note_graph(first_content=first_content, trigger_type=trigger_type),
        ),
    )


def test_claimable_query_filters_before_limit_and_orders_oldest_first(seeded_session) -> None:
    now = shanghai_now()
    oldest = _create_run(seeded_session, available_at=now - timedelta(minutes=2))
    newer = _create_run(seeded_session, available_at=now - timedelta(minutes=1))
    for _ in range(60):
        _create_run(seeded_session, status="completed", available_at=now)

    claimed_candidates = repository.list_claimable_agent_runs(seeded_session, now=now, limit=50)

    assert [item.id for item in claimed_candidates] == [oldest.id, newer.id]


def test_immediate_run_executes_only_the_newly_created_run(seeded_session) -> None:
    workflow = _create_workflow(seeded_session, key="targeted_immediate_workflow")
    older_run_ids = [
        runs.enqueue_workflow_run(
            seeded_session,
            workflow_key=workflow.key,
            trigger_kind="manual",
            trigger_event="manual",
            target_type=None,
            target_id=None,
        ).id
        for _ in range(2)
    ]

    created = runs.create_workflow_run(
        seeded_session,
        get_automation_runtime(),
        workflow_key=workflow.key,
        payload=AgentWorkflowRunCreateWrite(
            trigger_binding_id="manual-trigger",
            execute_immediately=True,
        ),
    )

    seeded_session.expire_all()
    older_runs = [repository.get_agent_run(seeded_session, run_id) for run_id in older_run_ids]
    assert created.run.status == "completed"
    assert all(item is not None and item.status == "queued" for item in older_runs)


def test_run_principal_is_persisted_and_missing_capability_scope_is_denied(seeded_session) -> None:
    workflow = _create_workflow(seeded_session, key="scoped_execution_workflow")
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
                        "id": "read-config",
                        "type": "operation.capability",
                        "label": "Read config",
                        "position": {"x": 240, "y": 0},
                        "config": {"operation_key": "get_site_config"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "trigger",
                        "target": "read-config",
                        "type": "default",
                        "config": {},
                    }
                ],
            }
        ),
    )
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
        principal=runs.RunPrincipal(
            principal_type="api_key",
            principal_id="limited-key",
            scopes=("automation:write",),
        ),
    )

    assert (
        runs.execute_due_runs(
            seeded_session,
            get_automation_runtime(),
            worker_id="scope-test-worker",
        )
        == 1
    )
    seeded_session.expire_all()
    persisted = repository.get_agent_run(seeded_session, queued.id)

    assert persisted is not None
    assert persisted.requested_by_type == "api_key"
    assert persisted.requested_by_id == "limited-key"
    assert persisted.authorization_scopes == ["automation:write"]
    assert persisted.status == "failed"
    assert persisted.error_code == "PermissionDenied"


def test_conditional_claim_allows_only_one_worker(seeded_session) -> None:
    run = _create_run(seeded_session)
    factory = get_session_factory()
    with factory() as worker_a, factory() as worker_b:
        first = repository.claim_agent_run(
            worker_a,
            run_id=run.id,
            worker_id="worker-a",
            now=shanghai_now(),
            lease_seconds=120,
        )
        worker_a.commit()
        second = repository.claim_agent_run(
            worker_b,
            run_id=run.id,
            worker_id="worker-b",
            now=shanghai_now(),
            lease_seconds=120,
        )

        assert first is not None
        assert first.lease_owner == "worker-a"
        assert first.attempt_count == 1
        assert second is None


def test_heartbeat_and_owner_checked_lease_release(seeded_session) -> None:
    run = _create_run(seeded_session)
    claimed = repository.claim_agent_run(
        seeded_session,
        run_id=run.id,
        worker_id="worker-a",
        now=shanghai_now(),
        lease_seconds=30,
    )
    assert claimed is not None
    first_expiry = claimed.lease_expires_at
    seeded_session.commit()

    assert (
        repository.heartbeat_agent_run(
            seeded_session,
            run_id=run.id,
            worker_id="worker-b",
            now=shanghai_now(),
            lease_seconds=120,
        )
        is False
    )
    run.context_payload = {"pending_change": "must survive heartbeat"}
    assert (
        repository.heartbeat_agent_run(
            seeded_session,
            run_id=run.id,
            worker_id="worker-a",
            now=shanghai_now(),
            lease_seconds=120,
        )
        is True
    )
    seeded_session.commit()
    seeded_session.refresh(run)
    assert run.lease_expires_at != first_expiry
    assert run.context_payload == {"pending_change": "must survive heartbeat"}

    assert (
        repository.release_agent_run_lease(
            seeded_session,
            run_id=run.id,
            worker_id="worker-b",
        )
        is False
    )
    assert (
        repository.release_agent_run_lease(
            seeded_session,
            run_id=run.id,
            worker_id="worker-a",
        )
        is True
    )
    seeded_session.commit()
    seeded_session.refresh(run)
    assert run.lease_owner is None
    assert run.lease_expires_at is None
    assert run.heartbeat_at is None


def test_expired_lease_recovery_requeues_retryable_run(seeded_session) -> None:
    now = shanghai_now()
    run = _create_run(seeded_session, status="running")
    run.attempt_count = 1
    run.max_attempts = 3
    run.lease_owner = "dead-worker"
    run.heartbeat_at = now - timedelta(minutes=2)
    run.lease_expires_at = now - timedelta(minutes=1)
    seeded_session.commit()

    recovered = repository.recover_expired_agent_runs(seeded_session, now=now)
    seeded_session.commit()
    seeded_session.refresh(run)

    assert recovered == 1
    assert run.status == "queued"
    assert run.available_at is not None
    assert run.lease_owner is None
    assert run.lease_expires_at is None


def test_enqueue_freezes_complete_workflow_snapshot_and_fingerprint(seeded_session) -> None:
    workflow = _create_workflow(seeded_session)
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )
    persisted = repository.get_agent_run(seeded_session, queued.id)
    assert persisted is not None
    frozen_snapshot = dict(persisted.workflow_snapshot)

    update_agent_workflow(
        seeded_session,
        workflow_key=workflow.key,
        payload=AgentWorkflowUpdate(name="Changed after enqueue"),
    )
    seeded_session.refresh(persisted)

    assert persisted is not None
    assert persisted.workflow_snapshot == frozen_snapshot
    assert frozen_snapshot["name"] == "Original workflow"
    assert persisted.workflow_fingerprint == _snapshot_fingerprint(frozen_snapshot)


def test_enqueue_reuses_run_for_same_workflow_idempotency_key(seeded_session) -> None:
    workflow = _create_workflow(seeded_session, key="coordinator_dedupe")

    first = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="webhook",
        trigger_event="incoming",
        target_type=None,
        target_id=None,
        idempotency_key="request-123",
    )
    second = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="webhook",
        trigger_event="incoming",
        target_type=None,
        target_id=None,
        idempotency_key="request-123",
    )

    assert second.id == first.id
    assert (
        seeded_session.query(AgentRun)
        .filter(AgentRun.workflow_key == workflow.key, AgentRun.idempotency_key == "request-123")
        .count()
        == 1
    )


def test_cancel_queued_run_finishes_immediately(seeded_session) -> None:
    workflow = _create_workflow(seeded_session, key="coordinator_cancel")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )

    cancelled = runs.cancel_workflow_run(seeded_session, run_id=queued.id)

    assert cancelled.status == "cancelled"
    assert cancelled.cancel_requested_at is not None
    assert cancelled.finished_at is not None


def test_cancel_running_run_sets_cooperative_request(seeded_session) -> None:
    run = _create_run(seeded_session, status="running")

    cancelling = runs.cancel_workflow_run(seeded_session, run_id=run.id)

    assert cancelling.status == "running"
    assert cancelling.cancel_requested_at is not None


def test_node_boundary_cancel_helper_stops_requested_run(seeded_session) -> None:
    run = _create_run(seeded_session, status="running")
    run.cancel_requested_at = shanghai_now()
    seeded_session.commit()

    assert runs.cancel_run_at_node_boundary(seeded_session, run=run) is True
    seeded_session.refresh(run)
    assert run.status == "cancelled"
    assert run.finished_at is not None


def test_retry_creates_new_run_from_original_snapshot(seeded_session) -> None:
    workflow = _create_workflow(seeded_session, key="coordinator_retry")
    source_read = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type="post",
        target_id="post-1",
        input_payload={"payload": "original"},
        context_payload={"actor": "admin"},
        principal=runs.RunPrincipal(
            principal_type="admin",
            principal_id="admin-1",
            scopes=("automation:write", "content:write"),
        ),
    )
    source = repository.get_agent_run(seeded_session, source_read.id)
    assert source is not None
    source.status = "failed"
    source.finished_at = shanghai_now()
    source.error_code = "SyntheticFailure"
    seeded_session.commit()

    retried = runs.retry_workflow_run(seeded_session, run_id=source.id)
    retry_model = repository.get_agent_run(seeded_session, retried.id)
    assert retry_model is not None

    assert retried.id != source.id
    assert retried.retry_of_run_id == source.id
    assert retried.status == "queued"
    assert retry_model.workflow_snapshot == source.workflow_snapshot
    assert retry_model.workflow_fingerprint == source.workflow_fingerprint
    assert retried.input_payload == source.input_payload
    assert retried.context_payload == source.context_payload
    assert retried.target_type == source.target_type
    assert retried.target_id == source.target_id
    assert retry_model.requested_by_type == source.requested_by_type
    assert retry_model.requested_by_id == source.requested_by_id
    assert retry_model.authorization_scopes == source.authorization_scopes


def test_retry_upgrades_legacy_embedded_workflow_snapshot(seeded_session) -> None:
    legacy_snapshot = {"key": "legacy_workflow", "name": "Legacy frozen workflow", "graph": {"nodes": []}}
    source = AgentRun(
        workflow_key="legacy_workflow",
        status="failed",
        trigger_kind="manual",
        thread_id=uuid4().hex,
        input_payload={"workflow_config_snapshot": legacy_snapshot},
        workflow_snapshot={},
        finished_at=shanghai_now(),
    )
    seeded_session.add(source)
    seeded_session.commit()

    retried = runs.retry_workflow_run(seeded_session, run_id=source.id)
    retry_model = repository.get_agent_run(seeded_session, retried.id)

    assert retry_model is not None
    assert retry_model.workflow_snapshot == legacy_snapshot
    assert retry_model.workflow_fingerprint == _snapshot_fingerprint(legacy_snapshot)


def test_runtime_cancels_before_second_graph_node(seeded_session, monkeypatch) -> None:
    workflow = _create_note_workflow(seeded_session, key="boundary_cancel_workflow")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )
    executed_nodes: list[str] = []
    original_execute = runtime_module._execute_graph_node

    def execute_and_request_cancel(state, *, node_id, node_type, node_config):
        executed_nodes.append(node_id)
        result = original_execute(state, node_id=node_id, node_type=node_type, node_config=node_config)
        if node_id == "first-note":
            with get_session_factory()() as cancellation_session:
                cancelling = repository.get_agent_run(cancellation_session, queued.id)
                assert cancelling is not None
                cancelling.cancel_requested_at = shanghai_now()
                cancellation_session.commit()
        return result

    monkeypatch.setattr(runtime_module, "_execute_graph_node", execute_and_request_cancel)

    processed = runs.execute_due_runs(
        seeded_session,
        get_automation_runtime(),
        worker_id="boundary-cancel-worker",
        lease_seconds=120,
    )
    seeded_session.expire_all()
    persisted = repository.get_agent_run(seeded_session, queued.id)

    assert processed == 1
    assert persisted is not None
    assert persisted.status == "cancelled"
    assert "first-note" in executed_nodes
    assert "second-note" not in executed_nodes


def test_runtime_heartbeats_before_each_graph_node(seeded_session, monkeypatch) -> None:
    workflow = _create_note_workflow(seeded_session, key="boundary_heartbeat_workflow")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )
    stale_heartbeat = shanghai_now() - timedelta(hours=1)
    heartbeat_seen_before_second = []
    original_execute = runtime_module._execute_graph_node

    def execute_and_observe_heartbeat(state, *, node_id, node_type, node_config):
        if node_id == "second-note":
            with get_session_factory()() as observation_session:
                observed = repository.get_agent_run(observation_session, queued.id)
                assert observed is not None
                heartbeat_seen_before_second.append(observed.heartbeat_at)
        result = original_execute(state, node_id=node_id, node_type=node_type, node_config=node_config)
        if node_id == "first-note":
            with get_session_factory()() as mutation_session:
                mutated = repository.get_agent_run(mutation_session, queued.id)
                assert mutated is not None
                mutated.heartbeat_at = stale_heartbeat
                mutation_session.commit()
        return result

    monkeypatch.setattr(runtime_module, "_execute_graph_node", execute_and_observe_heartbeat)

    processed = runs.execute_due_runs(
        seeded_session,
        get_automation_runtime(),
        worker_id="boundary-heartbeat-worker",
        lease_seconds=120,
    )

    assert processed == 1
    assert len(heartbeat_seen_before_second) == 1
    observed_heartbeat = heartbeat_seen_before_second[0]
    assert observed_heartbeat is not None
    assert observed_heartbeat.replace(tzinfo=None) != stale_heartbeat.replace(tzinfo=None)


def test_runtime_failure_uses_fresh_session_after_original_session_is_invalid(seeded_session) -> None:
    workflow = _create_note_workflow(seeded_session, key="fresh_failure_workflow")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )

    class InvalidatingRuntime:
        def invoke(self, _state, *, thread_id, **_kwargs):
            assert thread_id
            try:
                seeded_session.execute(
                    insert(AgentRun).values(
                        id=queued.id,
                        workflow_key=workflow.key,
                        status="queued",
                        trigger_kind="manual",
                        thread_id=uuid4().hex,
                    )
                )
            except IntegrityError:
                raise RuntimeError("runtime invalidated the coordinator session") from None
            raise AssertionError("duplicate insert must fail")

    processed = runs.execute_due_runs(
        seeded_session,
        InvalidatingRuntime(),
        worker_id="fresh-failure-worker",
        lease_seconds=120,
    )
    seeded_session.expire_all()
    persisted = repository.get_agent_run(seeded_session, queued.id)

    assert processed == 1
    assert persisted is not None
    assert persisted.status == "failed"
    assert persisted.error_code == "RuntimeError"
    assert persisted.lease_owner is None


def test_runtime_failure_preserves_lease_when_fresh_persistence_is_unavailable(
    seeded_session,
    monkeypatch,
) -> None:
    workflow = _create_note_workflow(seeded_session, key="unavailable_failure_persistence_workflow")
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )
    real_factory = get_session_factory()

    class FailingRuntime:
        def invoke(self, _state, *, thread_id, **_kwargs):
            assert thread_id
            raise RuntimeError("runtime failed before persistence became unavailable")

    class UnavailableSessionFactory:
        def __call__(self):
            raise RuntimeError("fresh persistence unavailable")

    monkeypatch.setattr(runs, "get_session_factory", lambda: UnavailableSessionFactory(), raising=False)

    processed = runs.execute_due_runs(
        seeded_session,
        FailingRuntime(),
        worker_id="unavailable-persistence-worker",
        lease_seconds=120,
    )

    with real_factory() as inspection_session:
        persisted = repository.get_agent_run(inspection_session, queued.id)
        assert persisted is not None
        assert persisted.status == "running"
        assert persisted.lease_owner == "unavailable-persistence-worker"
        assert persisted.lease_expires_at is not None
    assert processed == 0


def test_identical_webhook_bodies_without_stable_event_id_create_distinct_runs(seeded_session, monkeypatch) -> None:
    workflow = _create_note_workflow(seeded_session, key="webhook_distinct_workflow", webhook=True)
    monkeypatch.setattr(runs, "execute_run_now", lambda *_args, **_kwargs: False)

    first = runs.trigger_webhook_workflow(
        seeded_session,
        object(),
        workflow_key=workflow.key,
        binding_id="incoming-hook",
        provided_secret="test-secret-123456",
        body={"payload": {"value": "same"}},
    )
    second = runs.trigger_webhook_workflow(
        seeded_session,
        object(),
        workflow_key=workflow.key,
        binding_id="incoming-hook",
        provided_secret="test-secret-123456",
        body={"payload": {"value": "same"}},
    )

    assert first.run is not None
    assert second.run is not None
    assert first.run.id != second.run.id


@pytest.mark.parametrize("stable_id_field", ["event_id", "delivery_id"])
def test_webhook_stable_body_id_is_idempotent_without_header(
    seeded_session,
    monkeypatch,
    stable_id_field: str,
) -> None:
    workflow = _create_note_workflow(
        seeded_session,
        key=f"webhook_{stable_id_field}_dedupe_workflow",
        webhook=True,
    )
    monkeypatch.setattr(runs, "execute_run_now", lambda *_args, **_kwargs: False)

    first = runs.trigger_webhook_workflow(
        seeded_session,
        object(),
        workflow_key=workflow.key,
        binding_id="incoming-hook",
        provided_secret="test-secret-123456",
        body={stable_id_field: "event-123", "payload": {"value": "same"}},
    )
    second = runs.trigger_webhook_workflow(
        seeded_session,
        object(),
        workflow_key=workflow.key,
        binding_id="incoming-hook",
        provided_secret="test-secret-123456",
        body={stable_id_field: "event-123", "payload": {"value": "changed"}},
    )

    assert first.run is not None
    assert second.run is not None
    assert first.run.id == second.run.id


def test_webhook_explicit_idempotency_key_takes_precedence(seeded_session, monkeypatch) -> None:
    workflow = _create_note_workflow(seeded_session, key="webhook_explicit_dedupe_workflow", webhook=True)
    monkeypatch.setattr(runs, "execute_run_now", lambda *_args, **_kwargs: False)

    first = runs.trigger_webhook_workflow(
        seeded_session,
        object(),
        workflow_key=workflow.key,
        binding_id="incoming-hook",
        provided_secret="test-secret-123456",
        body={"event_id": "event-1", "payload": {"value": "same"}},
        idempotency_key="delivery-attempt-123",
    )
    second = runs.trigger_webhook_workflow(
        seeded_session,
        object(),
        workflow_key=workflow.key,
        binding_id="incoming-hook",
        provided_secret="test-secret-123456",
        body={"event_id": "event-2", "payload": {"value": "changed"}},
        idempotency_key="delivery-attempt-123",
    )

    assert first.run is not None
    assert second.run is not None
    assert first.run.id == second.run.id


def test_fifty_waiting_runs_do_not_starve_next_runnable_run(seeded_session) -> None:
    now = shanghai_now()
    timeout_at = now + timedelta(hours=1)
    waiting_ids: set[str] = set()
    for index in range(50):
        waiting = _create_run(
            seeded_session,
            workflow_key=f"waiting-{index}",
            status="running",
            available_at=now,
        )
        runs._finalize_interrupt(
            seeded_session,
            run=waiting,
            first_interrupt=None,
            interrupt_payload={
                "kind": "wait",
                "wait_type": "event",
                "node_id": "wait-event",
                "event_type": "coordinator.signal",
                "timeout_at": timeout_at.isoformat(),
            },
        )
        waiting_ids.add(waiting.id)
    seeded_session.commit()
    runnable = _create_run(seeded_session, workflow_key="runnable-after-waits", available_at=now)

    candidates = repository.list_claimable_agent_runs(seeded_session, now=now, limit=50)
    candidate_ids = {item.id for item in candidates}

    assert runnable.id in candidate_ids
    assert candidate_ids.isdisjoint(waiting_ids)


def test_event_resume_makes_waiting_run_immediately_available(seeded_session) -> None:
    now = shanghai_now()
    waiting = _create_run(
        seeded_session,
        workflow_key="event-resume-workflow",
        status="running",
        available_at=now + timedelta(hours=2),
    )
    runs._finalize_interrupt(
        seeded_session,
        run=waiting,
        first_interrupt=None,
        interrupt_payload={
            "kind": "wait",
            "wait_type": "event",
            "node_id": "wait-event",
            "event_type": "coordinator.signal",
            "timeout_at": (now + timedelta(hours=1)).isoformat(),
        },
    )
    seeded_session.commit()

    runs.emit_event(
        seeded_session,
        AutomationEvent(
            event_type="coordinator.signal",
            event_id="signal-1",
            target_type="post",
            target_id="post-1",
            payload={"ok": True},
        ),
    )
    seeded_session.refresh(waiting)

    assert "resume_value" in waiting.input_payload
    assert waiting.available_at is not None
    assert waiting.available_at.replace(tzinfo=None) <= shanghai_now().replace(tzinfo=None)


def test_normal_wait_cycles_reset_execution_attempt_budget(seeded_session) -> None:
    run = _create_run(seeded_session, workflow_key="repeated-wait-workflow")
    run.max_attempts = 1
    seeded_session.commit()

    for cycle in range(3):
        claimed = repository.claim_agent_run(
            seeded_session,
            run_id=run.id,
            worker_id=f"wait-worker-{cycle}",
            now=shanghai_now(),
            lease_seconds=120,
        )
        assert claimed is not None
        seeded_session.commit()
        runs._finalize_interrupt(
            seeded_session,
            run=claimed,
            first_interrupt=None,
            interrupt_payload={
                "kind": "wait",
                "wait_type": "delay",
                "node_id": f"wait-{cycle}",
                "resume_at": shanghai_now().isoformat(),
                "attempt": cycle + 1,
            },
        )
        seeded_session.commit()
        seeded_session.refresh(run)
        assert run.status == "queued"
        assert run.attempt_count == 0


def test_cancel_terminal_run_raises_state_conflict(seeded_session) -> None:
    completed = _create_run(seeded_session, status="completed")

    with pytest.raises(StateConflict):
        runs.cancel_workflow_run(seeded_session, run_id=completed.id)


def test_cancel_terminal_run_api_returns_409(client, admin_headers) -> None:
    with get_session_factory()() as session:
        completed = AgentRun(
            workflow_key="completed-api-workflow",
            status="completed",
            trigger_kind="manual",
            thread_id=uuid4().hex,
            available_at=shanghai_now(),
        )
        session.add(completed)
        session.commit()
        run_id = completed.id

    response = client.post(
        f"/api/v1/admin/automation/runs/{run_id}/cancel",
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_execution_uses_frozen_snapshot_after_pack_update(seeded_session) -> None:
    workflow = _create_note_workflow(
        seeded_session,
        key="frozen_snapshot_execution_workflow",
        first_content="original snapshot content",
    )
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )
    update_agent_workflow(
        seeded_session,
        workflow_key=workflow.key,
        payload=AgentWorkflowUpdate(
            graph=_note_graph(first_content="changed pack content", trigger_type="trigger.manual")
        ),
    )

    processed = runs.execute_due_runs(
        seeded_session,
        get_automation_runtime(),
        worker_id="snapshot-worker",
    )
    _run, steps = runs.get_run_detail(seeded_session, queued.id)
    first_note = next(step for step in steps if step.node_key == "first-note")

    assert processed == 1
    assert first_note.output_payload["content"] == "original snapshot content"


def test_agent_run_status_does_not_advertise_unimplemented_retry_scheduled() -> None:
    assert "retry_scheduled" not in get_args(AutomationStatus)


def test_run_state_rejects_illegal_terminal_transition() -> None:
    from aerisun.domain.automation import run_state

    assert run_state.is_terminal_run_status("completed") is True
    assert run_state.is_legal_run_transition("queued", "running") is True
    with pytest.raises(StateConflict):
        run_state.ensure_legal_run_transition("completed", "running")

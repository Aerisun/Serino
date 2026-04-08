"""Run scheduling, execution, and querying."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from aerisun.core.time import BEIJING_TZ, normalize_shanghai_datetime, shanghai_now
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation._helpers import fallback_workflow_config
from aerisun.domain.automation.models import AgentRun
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import (
    AgentRunRead,
    AgentRunStepRead,
    AgentWorkflowRead,
    AgentWorkflowRunCreateRead,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowWebhookTriggerRead,
)
from aerisun.domain.automation.settings import (
    find_agent_workflow,
    find_workflow_trigger_binding,
    get_agent_model_config,
    get_agent_workflow,
    list_workflow_bindings_by_type,
)
from aerisun.domain.automation.validation import compile_workflow
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

if TYPE_CHECKING:
    from aerisun.domain.automation.models import AutomationEvent

logger = logging.getLogger(__name__)


def enqueue_workflow_run(
    session: Session,
    *,
    workflow_key: str,
    trigger_kind: str,
    trigger_event: str | None,
    target_type: str | None,
    target_id: str | None,
    input_payload: dict[str, Any] | None = None,
    context_payload: dict[str, Any] | None = None,
    autocommit: bool = True,
) -> AgentRunRead:
    run = repo.create_agent_run(
        session,
        workflow_key=workflow_key,
        trigger_kind=trigger_kind,
        trigger_event=trigger_event,
        target_type=target_type,
        target_id=target_id,
        input_payload=input_payload,
        context_payload=context_payload,
        thread_id=uuid4().hex,
    )
    if autocommit:
        session.commit()
        session.refresh(run)
    else:
        session.flush()
    return AgentRunRead.model_validate(run)


def list_runs(session: Session) -> list[AgentRunRead]:
    return [AgentRunRead.model_validate(item) for item in repo.list_agent_runs(session)]


def get_run_detail(session: Session, run_id: str) -> tuple[AgentRunRead, list[AgentRunStepRead]]:
    run = repo.get_agent_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    steps = repo.list_agent_run_steps(session, run_id=run_id)
    return AgentRunRead.model_validate(run), [AgentRunStepRead.model_validate(step) for step in steps]


def _select_trigger_binding(
    workflow: AgentWorkflowRead,
    payload: AgentWorkflowRunCreateWrite | None,
    *,
    preferred_type: str | None = None,
):
    binding_id = str((payload.trigger_binding_id if payload else "") or "").strip()
    if binding_id:
        return next((item for item in workflow.trigger_bindings if item.id == binding_id and item.enabled), None)
    if preferred_type:
        binding = next(
            (item for item in workflow.trigger_bindings if item.enabled and item.type == preferred_type), None
        )
        if binding is not None:
            return binding
    return next((item for item in workflow.trigger_bindings if item.enabled), None)


def _run_trigger_event(binding, payload: AgentWorkflowRunCreateWrite | None) -> str:
    if payload and payload.trigger_event:
        return payload.trigger_event
    config = dict(binding.config or {}) if binding is not None else {}
    return str(config.get("event_type") or config.get("path") or (binding.type if binding is not None else "manual"))


def _run_target_type(binding, payload: AgentWorkflowRunCreateWrite | None) -> str | None:
    if payload and payload.target_type:
        return payload.target_type
    config = dict(binding.config or {}) if binding is not None else {}
    return str(config.get("target_type") or "").strip() or None


def create_workflow_run(
    session: Session,
    runtime: AutomationRuntime,
    *,
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite,
    trigger_kind: str = "manual",
) -> AgentWorkflowRunCreateRead:
    workflow = get_agent_workflow(session, workflow_key)
    validation = compile_workflow(workflow.model_dump(mode="json"), session=session)
    if not validation.ok:
        raise ValidationError("Workflow validation failed")
    binding = _select_trigger_binding(
        workflow, payload, preferred_type=f"trigger.{trigger_kind}" if trigger_kind else None
    )
    queued = enqueue_workflow_run(
        session,
        workflow_key=workflow.key,
        trigger_kind=trigger_kind,
        trigger_event=_run_trigger_event(binding, payload),
        target_type=_run_target_type(binding, payload),
        target_id=payload.target_id,
        input_payload={
            **dict(payload.input_payload or {}),
            "trigger_binding_id": binding.id if binding is not None else None,
        },
        context_payload=dict(payload.context_payload or {}),
        autocommit=True,
    )
    if payload.execute_immediately:
        execute_due_runs(session, runtime)
    run, steps = get_run_detail(session, queued.id)
    return AgentWorkflowRunCreateRead(run=run, steps=steps, validation=validation)


def test_workflow_run(
    session: Session,
    runtime: AutomationRuntime,
    *,
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite,
) -> AgentWorkflowRunCreateRead:
    return create_workflow_run(session, runtime, workflow_key=workflow_key, payload=payload, trigger_kind="manual")


def trigger_webhook_workflow(
    session: Session,
    runtime: AutomationRuntime,
    *,
    workflow_key: str,
    binding_id: str,
    provided_secret: str,
    body: dict[str, Any] | None,
) -> AgentWorkflowWebhookTriggerRead:
    workflow, binding = find_workflow_trigger_binding(session, workflow_key=workflow_key, binding_id=binding_id)
    config = dict(binding.config or {})
    expected_secret = str(config.get("secret") or "").strip()
    if expected_secret and provided_secret != expected_secret:
        raise ValidationError("Invalid webhook trigger secret")
    payload = AgentWorkflowRunCreateWrite(
        trigger_binding_id=binding.id,
        trigger_event=str(config.get("event_type") or config.get("path") or f"webhook:{binding.id}"),
        target_type=str(config.get("target_type") or "").strip() or None,
        target_id=str((body or {}).get("target_id") or ""),
        context_payload=dict(body or {}),
        input_payload={"trigger_binding_id": binding.id},
        execute_immediately=True,
    )
    created = create_workflow_run(session, runtime, workflow_key=workflow.key, payload=payload, trigger_kind="webhook")
    return AgentWorkflowWebhookTriggerRead(
        ok=True,
        run=created.run,
        accepted=True,
        summary="Webhook trigger accepted.",
    )


# ---------------------------------------------------------------------------
# Run execution internals
# ---------------------------------------------------------------------------


def _mark_run_cancelled(
    session: Session,
    *,
    run: AgentRun,
    sequence_no: int,
    narrative: str,
    reason: str,
) -> None:
    run.status = "cancelled"
    run.finished_at = shanghai_now()
    run.result_payload = {"skipped": True, "reason": reason, "workflow_key": run.workflow_key}
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=sequence_no,
        node_key="workflow_dispatch",
        step_kind="node_cancelled",
        status="cancelled",
        narrative=narrative,
        output_payload=run.result_payload,
        finished_at=shanghai_now(),
    )


def _mark_run_failed(
    session: Session,
    *,
    run: AgentRun,
    sequence_no: int,
    narrative: str,
    error_code: str,
    error_message: str,
) -> None:
    run.status = "failed"
    run.finished_at = shanghai_now()
    run.error_code = error_code
    run.error_message = error_message
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=sequence_no,
        node_key="workflow_dispatch",
        step_kind="node_failed",
        status="failed",
        narrative=narrative,
        error_payload={"error_code": run.error_code, "error_message": run.error_message},
        finished_at=shanghai_now(),
    )


def _extract_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result_payload")
    return payload if isinstance(payload, dict) else result


def _extract_execution_trace(result: dict[str, Any], snapshot: Any | None = None) -> list[dict[str, Any]]:
    payload = result.get("execution_trace")
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    snapshot_values = getattr(snapshot, "values", None)
    if isinstance(snapshot_values, dict):
        trace = snapshot_values.get("execution_trace")
        if isinstance(trace, list):
            return [dict(item) for item in trace if isinstance(item, dict)]
    return []


def _next_run_sequence_no(session: Session, run_id: str) -> int:
    steps = repo.list_agent_run_steps(session, run_id=run_id)
    return (steps[-1].sequence_no if steps else 0) + 1


def _persist_graph_trace_steps(session: Session, run: AgentRun, trace: list[dict[str, Any]]) -> None:
    existing_steps = repo.list_agent_run_steps(session, run_id=run.id)
    persisted_count = len([item for item in existing_steps if item.step_kind == "graph_node_completed"])
    next_sequence = (existing_steps[-1].sequence_no if existing_steps else 0) + 1
    for entry in trace[persisted_count:]:
        finished_at_raw = entry.get("finished_at")
        finished_at = None
        if isinstance(finished_at_raw, str):
            try:
                finished_at = normalize_shanghai_datetime(datetime.fromisoformat(finished_at_raw))
            except ValueError:
                finished_at = shanghai_now()
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=next_sequence,
            node_key=str(entry.get("node_key") or "graph_node"),
            step_kind="graph_node_completed",
            status=str(entry.get("status") or "completed"),
            narrative=str(entry.get("narrative") or "图节点已完成执行。"),
            input_payload=dict(entry.get("input_payload") or {}),
            output_payload=dict(entry.get("output_payload") or {}),
            error_payload=dict(entry.get("error_payload") or {}),
            finished_at=finished_at or shanghai_now(),
        )
        next_sequence += 1


def _workflow_snapshot_payload(workflow_config: AgentWorkflowRead) -> dict[str, Any]:
    return workflow_config.model_dump(mode="json")


def _run_workflow_snapshot(run: AgentRun, fallback: AgentWorkflowRead) -> dict[str, Any]:
    snapshot = dict(run.input_payload.get("workflow_config_snapshot") or {})
    if snapshot:
        return snapshot
    return fallback.model_dump(mode="json")


def _workflow_requires_ai(workflow_snapshot: dict[str, Any]) -> bool:
    return any(
        str(item.get("type") or "") in {"ai.task", "ai_task"}
        for item in list(dict(workflow_snapshot.get("graph") or {}).get("nodes") or [])
        if isinstance(item, dict)
    )


def _pending_wait_payload(run: AgentRun) -> dict[str, Any]:
    return dict(run.input_payload.get("pending_wait") or {})


def _next_resume_value(run: AgentRun, *, now: datetime) -> dict[str, Any] | None:
    input_payload = dict(run.input_payload or {})
    pending_wait = _pending_wait_payload(run)
    queued_resume = input_payload.get("resume_value")
    if isinstance(queued_resume, dict):
        return dict(queued_resume)
    if not pending_wait:
        return None
    wait_type = str(pending_wait.get("wait_type") or "").strip()
    if wait_type in {"delay", "poll"}:
        resume_at_raw = str(pending_wait.get("resume_at") or "").strip()
        if resume_at_raw:
            try:
                resume_at = normalize_shanghai_datetime(datetime.fromisoformat(resume_at_raw))
            except ValueError:
                resume_at = now
            if resume_at > now:
                return None
        return {"resumed_at": now.isoformat(), "attempt": pending_wait.get("attempt")}
    if wait_type == "event":
        timeout_at_raw = str(pending_wait.get("timeout_at") or "").strip()
        if timeout_at_raw:
            try:
                timeout_at = normalize_shanghai_datetime(datetime.fromisoformat(timeout_at_raw))
            except ValueError:
                timeout_at = now
            if timeout_at <= now:
                return {"timeout": True, "resumed_at": now.isoformat()}
        return None
    if wait_type == "gate":
        return None
    return {"resumed_at": now.isoformat()}


def _run_state_payload(
    run: AgentRun, workflow_snapshot: dict[str, Any], model_config: dict[str, Any]
) -> dict[str, Any]:
    input_payload = dict(run.input_payload or {})
    return {
        "run_id": run.id,
        "workflow_key": run.workflow_key,
        "trigger_kind": run.trigger_kind,
        "trigger_event": run.trigger_event,
        "target_type": run.target_type,
        "target_id": run.target_id,
        "inputs": dict(input_payload),
        "context_payload": dict(run.context_payload or {}),
        "workflow_config": workflow_snapshot,
        "model_config": model_config,
    }


def _finalize_interrupt(
    session: Session,
    *,
    run: AgentRun,
    first_interrupt: Any,
    interrupt_payload: dict[str, Any],
) -> None:
    interrupt_node_key = str(interrupt_payload.get("node_id") or "workflow_interrupt")
    kind = str(interrupt_payload.get("kind") or "approval")
    if kind == "approval":
        run.status = "awaiting_approval"
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=_next_run_sequence_no(session, run.id),
            node_key=interrupt_node_key,
            step_kind="interrupt_requested",
            status="interrupted",
            narrative="工作流请求人工审批。",
            output_payload={"request": interrupt_payload},
            finished_at=shanghai_now(),
        )
        interrupt_id = getattr(first_interrupt, "id", None) or f"{run.id}:approval"
        repo.create_agent_run_approval(
            session,
            run_id=run.id,
            step_id=None,
            interrupt_id=interrupt_id,
            node_key=interrupt_node_key,
            approval_type=str(interrupt_payload.get("approval_type") or "manual_review"),
            request_payload={"value": interrupt_payload},
        )
        return

    if kind == "wait":
        input_payload = dict(run.input_payload or {})
        input_payload["pending_wait"] = interrupt_payload
        input_payload.pop("resume_value", None)
        run.input_payload = input_payload
        run.status = "queued"
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=_next_run_sequence_no(session, run.id),
            node_key=interrupt_node_key,
            step_kind="interrupt_requested",
            status="interrupted",
            narrative="工作流进入等待状态。",
            output_payload={"request": interrupt_payload},
            finished_at=shanghai_now(),
        )
        return

    raise ValidationError(f"Unsupported workflow interrupt kind: {kind}")


def _complete_run_from_result(session: Session, *, run: AgentRun, result: dict[str, Any]) -> None:
    run.status = "completed"
    run.finished_at = shanghai_now()
    run.result_payload = _extract_result_payload(result)
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=_next_run_sequence_no(session, run.id),
        node_key="workflow_complete",
        step_kind="node_completed",
        status="completed",
        narrative="工作流已完成。",
        output_payload=run.result_payload,
        finished_at=shanghai_now(),
    )


def _execute_one_run(session: Session, runtime: AutomationRuntime, run: AgentRun) -> bool:
    now = shanghai_now()
    resume_value = _next_resume_value(run, now=now)
    pending_wait = _pending_wait_payload(run)
    if pending_wait and resume_value is None:
        return False

    run.status = "running"
    run.started_at = run.started_at or now
    session.commit()
    if not repo.list_agent_run_steps(session, run_id=run.id):
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=1,
            node_key="workflow_dispatch",
            step_kind="node_entered",
            status="running",
            narrative=f"开始执行工作流 {run.workflow_key}。",
            input_payload=run.input_payload,
            started_at=now,
        )
        session.commit()

    workflow_config = find_agent_workflow(session, run.workflow_key) or fallback_workflow_config(run)
    workflow_snapshot = _workflow_snapshot_payload(workflow_config)
    input_payload = dict(run.input_payload or {})
    input_payload["workflow_config_snapshot"] = workflow_snapshot
    if resume_value is not None:
        input_payload["resume_value"] = resume_value
    run.input_payload = input_payload

    model_config = get_agent_model_config(session)
    if _workflow_requires_ai(workflow_snapshot):
        if not model_config.enabled:
            _mark_run_cancelled(
                session,
                run=run,
                sequence_no=_next_run_sequence_no(session, run.id),
                narrative="Agent 模型开关已关闭，当前工作流不执行。",
                reason="model_disabled",
            )
            session.commit()
            return True
        if not model_config.is_ready:
            _mark_run_failed(
                session,
                run=run,
                sequence_no=_next_run_sequence_no(session, run.id),
                narrative="Agent 模型配置不完整，无法执行工作流。",
                error_code="ModelConfigNotReady",
                error_message="Agent model config is not ready",
            )
            session.commit()
            return True
        if model_config.provider != "openai_compatible":
            _mark_run_failed(
                session,
                run=run,
                sequence_no=_next_run_sequence_no(session, run.id),
                narrative="当前 Agent 模型服务商尚未接入执行链路。",
                error_code="UnsupportedModelProvider",
                error_message=f"Unsupported model provider: {model_config.provider}",
            )
            session.commit()
            return True

    try:
        if resume_value is not None and run.latest_checkpoint_id:
            result = runtime.resume(
                thread_id=run.thread_id,
                resume_value=resume_value,
                workflow_config=workflow_snapshot,
            )
            input_payload = dict(run.input_payload or {})
            input_payload.pop("pending_wait", None)
            input_payload.pop("resume_value", None)
            run.input_payload = input_payload
        else:
            result = runtime.invoke(
                _run_state_payload(run, workflow_snapshot, model_config.model_dump(exclude={"is_ready"})),
                thread_id=run.thread_id,
            )
        snapshot = runtime.get_state(thread_id=run.thread_id, workflow_config=workflow_snapshot)
        run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
        run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
        _persist_graph_trace_steps(session, run, _extract_execution_trace(result, snapshot))
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            first = interrupts[0]
            interrupt_value = getattr(first, "value", None) if first is not None else None
            interrupt_payload = dict(interrupt_value or {}) if isinstance(interrupt_value, dict) else {}
            _finalize_interrupt(session, run=run, first_interrupt=first, interrupt_payload=interrupt_payload)
        else:
            _complete_run_from_result(session, run=run, result=result)
    except Exception as exc:
        _mark_run_failed(
            session,
            run=run,
            sequence_no=_next_run_sequence_no(session, run.id),
            narrative="工作流执行失败。",
            error_code=exc.__class__.__name__,
            error_message=str(exc),
        )
    session.commit()
    return True


def _schedule_slot(config: dict[str, Any], *, now: datetime) -> tuple[bool, str]:
    interval_seconds = int(config.get("interval_seconds") or 0)
    if interval_seconds > 0:
        slot_start = int(now.timestamp()) // interval_seconds * interval_seconds
        return True, f"interval:{slot_start}"
    cron = str(config.get("cron") or "").strip()
    if cron:
        trigger = CronTrigger.from_crontab(cron, timezone=str(now.tzinfo or BEIJING_TZ))
        previous_window = now - timedelta(minutes=1)
        next_fire = trigger.get_next_fire_time(None, previous_window)
        if next_fire is not None and next_fire <= now:
            return True, f"cron:{next_fire.replace(second=0, microsecond=0).isoformat()}"
    return False, ""


def dispatch_due_schedule_runs(session: Session, *, now: datetime | None = None) -> int:
    current = normalize_shanghai_datetime(now) if now is not None else shanghai_now()
    existing_slots = {
        (
            item.workflow_key,
            str((item.input_payload or {}).get("trigger_binding_id") or ""),
            str((item.input_payload or {}).get("schedule_slot") or ""),
        )
        for item in repo.list_agent_runs(session, limit=200)
        if item.status in {"queued", "running", "awaiting_approval"}
    }
    created = 0
    for workflow, binding in list_workflow_bindings_by_type(session, binding_type="trigger.schedule"):
        config = dict(binding.config or {})
        due, slot = _schedule_slot(config, now=current)
        if not due:
            continue
        dedupe_key = (workflow.key, binding.id, slot)
        if dedupe_key in existing_slots:
            continue
        enqueue_workflow_run(
            session,
            workflow_key=workflow.key,
            trigger_kind="schedule",
            trigger_event=str(config.get("event_type") or f"schedule:{binding.id}"),
            target_type=str(config.get("target_type") or "").strip() or None,
            target_id=None,
            input_payload={"trigger_binding_id": binding.id, "schedule_slot": slot},
            context_payload={"scheduled_at": current.isoformat(), "binding_id": binding.id},
            autocommit=False,
        )
        existing_slots.add(dedupe_key)
        created += 1
    if created:
        session.commit()
    return created


def execute_due_runs(session: Session, runtime: AutomationRuntime) -> int:
    dispatch_due_schedule_runs(session)
    runs = [item for item in repo.list_agent_runs(session, limit=50) if item.status == "queued"]
    processed = 0
    for run in runs:
        if _execute_one_run(session, runtime, run):
            processed += 1
    return processed


def emit_event(session: Session, event: AutomationEvent) -> None:
    subscriptions = repo.list_active_webhook_subscriptions(session, event_type=event.event_type)
    for subscription in subscriptions:
        if subscription.event_types and event.event_type not in subscription.event_types:
            continue
        repo.create_webhook_delivery(session, subscription=subscription, event=event)

    for run in repo.list_agent_runs(session, limit=200):
        if run.status != "queued":
            continue
        pending_wait = _pending_wait_payload(run)
        if str(pending_wait.get("wait_type") or "") != "event":
            continue
        expected_event = str(pending_wait.get("event_type") or "").strip()
        expected_target = str(pending_wait.get("target_type") or "").strip()
        if expected_event and expected_event != event.event_type:
            continue
        if expected_target and expected_target != event.target_type:
            continue
        input_payload = dict(run.input_payload or {})
        input_payload["resume_value"] = {"event": event.model_dump()}
        run.input_payload = input_payload

    from aerisun.domain.automation.settings import list_workflows_for_event

    workflows = list_workflows_for_event(
        session,
        event_type=event.event_type,
        target_type=event.target_type,
    )
    for workflow in workflows:
        enqueue_workflow_run(
            session,
            workflow_key=workflow.key,
            trigger_kind="event",
            trigger_event=event.event_type,
            target_type=event.target_type,
            target_id=event.target_id,
            input_payload={"event_id": event.event_id},
            context_payload=event.payload,
            autocommit=False,
        )
    session.commit()

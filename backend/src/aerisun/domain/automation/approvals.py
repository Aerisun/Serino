"""Approval workflow helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from aerisun.core.time import shanghai_now
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation._helpers import fallback_workflow_config
from aerisun.domain.automation.runs import (
    _complete_run_from_result,
    _extract_execution_trace,
    _mark_run_failed,
    _next_run_sequence_no,
    _persist_graph_trace_steps,
    _run_workflow_snapshot,
)
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import AgentRunApprovalRead, AgentRunRead, ApprovalDecisionWrite
from aerisun.domain.automation.settings import find_agent_workflow
from aerisun.domain.exceptions import ResourceNotFound


def list_pending_approvals(session: Session) -> list[AgentRunApprovalRead]:
    return [AgentRunApprovalRead.model_validate(item) for item in repo.list_pending_approvals(session)]


def resolve_approval(
    session: Session,
    runtime: AutomationRuntime,
    *,
    approval_id: str,
    actor_id: str,
    decision_payload: ApprovalDecisionWrite | dict[str, Any],
) -> AgentRunRead:
    if isinstance(decision_payload, ApprovalDecisionWrite):
        decision_payload = decision_payload.model_dump(exclude_none=True)
    approval = repo.get_approval(session, approval_id)
    if approval is None:
        raise ResourceNotFound("Approval not found")
    run = repo.get_agent_run(session, approval.run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    approval.status = "approved" if (decision_payload.get("action") or "approve") != "reject" else "rejected"
    approval.response_payload = decision_payload
    approval.resolved_by_type = "admin"
    approval.resolved_by_id = actor_id
    approval.resolved_at = shanghai_now()
    workflow_config = find_agent_workflow(session, run.workflow_key) or fallback_workflow_config(run)
    workflow_snapshot = _run_workflow_snapshot(run, workflow_config)
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=_next_run_sequence_no(session, run.id),
        node_key=approval.node_key,
        step_kind="resume_requested",
        status="running",
        narrative="管理员已提交审批结果，准备恢复工作流。",
        input_payload=decision_payload,
        started_at=shanghai_now(),
    )
    session.commit()

    try:
        result = runtime.resume(
            thread_id=run.thread_id,
            resume_value=decision_payload,
            workflow_config=workflow_snapshot,
        )
        snapshot = runtime.get_state(thread_id=run.thread_id, workflow_config=workflow_snapshot)
        run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
        run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
        _persist_graph_trace_steps(session, run, _extract_execution_trace(result, snapshot))
        _complete_run_from_result(session, run=run, result=result)
    except Exception as exc:
        _mark_run_failed(
            session,
            run=run,
            sequence_no=_next_run_sequence_no(session, run.id),
            narrative="审批恢复后执行失败。",
            error_code=exc.__class__.__name__,
            error_message=str(exc),
        )
    session.commit()
    session.refresh(run)
    return AgentRunRead.model_validate(run)

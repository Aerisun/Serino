"""Approval workflow helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from aerisun.core.redaction import safe_exception_detail
from aerisun.core.time import shanghai_now
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation._helpers import fallback_workflow_config
from aerisun.domain.automation.run_state import is_terminal_run_status, transition_agent_run
from aerisun.domain.automation.runs import (
    _mark_run_failed,
    _next_run_sequence_no,
    _run_workflow_snapshot,
    reduce_runtime_result,
)
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import AgentRunApprovalRead, AgentRunRead, ApprovalDecisionWrite
from aerisun.domain.automation.settings import (
    agent_model_runtime_config,
    find_agent_workflow,
    get_agent_model_config_resolved,
)
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError


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
    action = str(decision_payload.get("action") or "approve").strip().lower()
    if action not in {"approve", "reject"}:
        raise ValidationError("Approval action must be approve or reject")
    decision_payload = {**decision_payload, "action": action}
    approval = repo.get_approval(session, approval_id)
    if approval is None:
        raise ResourceNotFound("Approval not found")
    run_id = approval.run_id
    resolved_at = shanghai_now()
    approval = repo.resolve_pending_approval(
        session,
        approval_id=approval_id,
        status="approved" if action == "approve" else "rejected",
        response_payload=decision_payload,
        resolved_by_type="admin",
        resolved_by_id=actor_id,
        resolved_at=resolved_at,
    )
    if approval is None:
        session.rollback()
        raise StateConflict("Approval was already resolved or its run is no longer awaiting approval")

    run = repo.get_agent_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    transition_agent_run(run, "running", at=resolved_at)
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
        started_at=resolved_at,
    )
    session.commit()

    model_config = get_agent_model_config_resolved(session)
    runtime_model_config = agent_model_runtime_config(model_config)
    known_model_secrets = (
        model_config.openai_compatible.api_key,
        model_config.openai_compatible.base_url,
    )
    try:
        result = runtime.resume(
            thread_id=run.thread_id,
            resume_value=decision_payload,
            workflow_config=workflow_snapshot,
            model_config=runtime_model_config,
        )
        reduce_runtime_result(
            session,
            runtime,
            run=run,
            result=result,
            workflow_snapshot=workflow_snapshot,
        )
    except Exception as exc:
        session.rollback()
        run = repo.get_agent_run(session, run_id)
        if run is None:
            raise ResourceNotFound("Agent run not found") from exc
        if is_terminal_run_status(run.status):
            raise
        _mark_run_failed(
            session,
            run=run,
            sequence_no=_next_run_sequence_no(session, run.id),
            narrative="审批恢复后执行失败。",
            error_code=exc.__class__.__name__,
            error_message=safe_exception_detail(exc, known_secrets=known_model_secrets),
        )
    session.commit()
    session.refresh(run)
    return AgentRunRead.model_validate(run)

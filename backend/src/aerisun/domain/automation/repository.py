from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from aerisun.core.time import shanghai_now
from aerisun.domain.automation.models import (
    AgentRun,
    AgentRunApproval,
    AgentRunStep,
    AutomationEvent,
    WebhookDeadLetter,
    WebhookDelivery,
    WebhookSubscription,
    WorkflowBuildTask,
    WorkflowBuildTaskStep,
    WorkflowGateBufferItem,
    WorkflowGateState,
)
from aerisun.domain.automation.run_state import ensure_legal_run_transition
from aerisun.domain.automation.secrets import protect_sensitive_data


def create_agent_run(
    session: Session,
    *,
    workflow_key: str,
    trigger_kind: str,
    trigger_event: str | None,
    target_type: str | None,
    target_id: str | None,
    input_payload: dict[str, Any] | None = None,
    context_payload: dict[str, Any] | None = None,
    thread_id: str,
    execution_mode: str = "live",
    workflow_snapshot: dict[str, Any] | None = None,
    workflow_fingerprint: str | None = None,
    idempotency_key: str | None = None,
    requested_by_type: str = "system",
    requested_by_id: str | None = None,
    authorization_scopes: list[str] | None = None,
    available_at: datetime | None = None,
    max_attempts: int = 3,
    retry_of_run_id: str | None = None,
) -> AgentRun:
    run = AgentRun(
        workflow_key=workflow_key,
        trigger_kind=trigger_kind,
        trigger_event=trigger_event,
        target_type=target_type,
        target_id=target_id,
        thread_id=thread_id,
        execution_mode=execution_mode,
        workflow_snapshot=workflow_snapshot or {},
        workflow_fingerprint=workflow_fingerprint,
        idempotency_key=idempotency_key,
        requested_by_type=requested_by_type,
        requested_by_id=requested_by_id,
        authorization_scopes=list(authorization_scopes or []),
        available_at=available_at,
        max_attempts=max_attempts,
        retry_of_run_id=retry_of_run_id,
        input_payload=protect_sensitive_data(input_payload or {}, purpose="automation-runtime-state"),
        context_payload=protect_sensitive_data(context_payload or {}, purpose="automation-runtime-state"),
    )
    session.add(run)
    return run


def get_workflow_gate_state(session: Session, *, workflow_key: str, node_id: str) -> WorkflowGateState | None:
    return (
        session.query(WorkflowGateState)
        .filter(WorkflowGateState.workflow_key == workflow_key, WorkflowGateState.node_id == node_id)
        .first()
    )


def get_or_create_workflow_gate_state(
    session: Session,
    *,
    workflow_key: str,
    node_id: str,
    default_status: str = "closed",
) -> WorkflowGateState:
    state = get_workflow_gate_state(session, workflow_key=workflow_key, node_id=node_id)
    if state is not None:
        return state
    state = WorkflowGateState(workflow_key=workflow_key, node_id=node_id, status=default_status)
    session.add(state)
    session.flush()
    return state


def get_gate_buffer_item_by_run(
    session: Session,
    *,
    workflow_key: str,
    node_id: str,
    run_id: str,
) -> WorkflowGateBufferItem | None:
    return (
        session.query(WorkflowGateBufferItem)
        .filter(
            WorkflowGateBufferItem.workflow_key == workflow_key,
            WorkflowGateBufferItem.node_id == node_id,
            WorkflowGateBufferItem.run_id == run_id,
        )
        .first()
    )


def create_gate_buffer_item(
    session: Session,
    *,
    workflow_key: str,
    node_id: str,
    run_id: str,
    payload: dict[str, Any] | None = None,
) -> WorkflowGateBufferItem:
    item = WorkflowGateBufferItem(
        workflow_key=workflow_key,
        node_id=node_id,
        run_id=run_id,
        payload=protect_sensitive_data(payload or {}, purpose="automation-runtime-state"),
    )
    session.add(item)
    session.flush()
    return item


def list_gate_buffer_items(
    session: Session,
    *,
    workflow_key: str,
    node_id: str,
    status: str | None = None,
) -> list[WorkflowGateBufferItem]:
    query = session.query(WorkflowGateBufferItem).filter(
        WorkflowGateBufferItem.workflow_key == workflow_key,
        WorkflowGateBufferItem.node_id == node_id,
    )
    if status:
        query = query.filter(WorkflowGateBufferItem.status == status)
    return list(query.order_by(WorkflowGateBufferItem.created_at.asc()).all())


def next_gate_buffer_item(session: Session, *, workflow_key: str, node_id: str) -> WorkflowGateBufferItem | None:
    return (
        session.query(WorkflowGateBufferItem)
        .filter(
            WorkflowGateBufferItem.workflow_key == workflow_key,
            WorkflowGateBufferItem.node_id == node_id,
            WorkflowGateBufferItem.status == "buffered",
        )
        .order_by(WorkflowGateBufferItem.created_at.asc())
        .first()
    )


def create_workflow_build_task(
    session: Session,
    *,
    workflow_key: str,
    task_type: str,
    summary: str = "",
) -> WorkflowBuildTask:
    task = WorkflowBuildTask(workflow_key=workflow_key, task_type=task_type, summary=summary)
    session.add(task)
    session.flush()
    return task


def add_workflow_build_task_step(
    session: Session,
    *,
    task_id: str,
    name: str,
    status: str,
    detail: str = "",
) -> WorkflowBuildTaskStep:
    step = WorkflowBuildTaskStep(task_id=task_id, name=name, status=status, detail=detail)
    session.add(step)
    session.flush()
    return step


def add_agent_run_step(
    session: Session,
    *,
    run_id: str,
    sequence_no: int,
    node_key: str,
    step_kind: str,
    status: str,
    narrative: str,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    error_payload: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> AgentRunStep:
    step = AgentRunStep(
        run_id=run_id,
        sequence_no=sequence_no,
        node_key=node_key,
        step_kind=step_kind,
        status=status,
        narrative=narrative,
        input_payload=protect_sensitive_data(input_payload or {}, purpose="automation-runtime-state"),
        output_payload=protect_sensitive_data(output_payload or {}, purpose="automation-runtime-state"),
        error_payload=protect_sensitive_data(error_payload or {}, purpose="automation-runtime-state"),
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(step)
    return step


def create_agent_run_approval(
    session: Session,
    *,
    run_id: str,
    step_id: str | None,
    interrupt_id: str,
    node_key: str,
    approval_type: str,
    request_payload: dict[str, Any] | None = None,
) -> AgentRunApproval:
    approval = AgentRunApproval(
        run_id=run_id,
        step_id=step_id,
        interrupt_id=interrupt_id,
        node_key=node_key,
        approval_type=approval_type,
        request_payload=protect_sensitive_data(request_payload or {}, purpose="automation-runtime-state"),
    )
    session.add(approval)
    return approval


def list_agent_runs(session: Session, *, limit: int = 50) -> list[AgentRun]:
    return list(session.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit).all())


def query_agent_runs(
    session: Session,
    *,
    statuses: list[str] | None = None,
    workflow_key: str | None = None,
    execution_mode: str | None = None,
    search: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    cursor_created_at: datetime | None = None,
    cursor_id: str | None = None,
    limit: int = 25,
) -> tuple[list[AgentRun], int, bool]:
    filters = []
    if statuses:
        filters.append(AgentRun.status.in_(statuses))
    if workflow_key:
        filters.append(AgentRun.workflow_key == workflow_key)
    if execution_mode:
        filters.append(AgentRun.execution_mode == execution_mode)
    if created_from is not None:
        filters.append(AgentRun.created_at >= created_from)
    if created_to is not None:
        filters.append(AgentRun.created_at <= created_to)
    if search:
        filters.append(
            or_(
                AgentRun.id.contains(search, autoescape=True),
                AgentRun.workflow_key.contains(search, autoescape=True),
                AgentRun.trigger_event.contains(search, autoescape=True),
                AgentRun.target_id.contains(search, autoescape=True),
                AgentRun.error_code.contains(search, autoescape=True),
                AgentRun.error_message.contains(search, autoescape=True),
            )
        )

    total = int(session.scalar(select(func.count()).select_from(AgentRun).where(*filters)) or 0)
    page_filters = list(filters)
    if cursor_created_at is not None and cursor_id:
        page_filters.append(
            or_(
                AgentRun.created_at < cursor_created_at,
                and_(AgentRun.created_at == cursor_created_at, AgentRun.id < cursor_id),
            )
        )
    rows = list(
        session.scalars(
            select(AgentRun)
            .where(*page_filters)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
            .limit(limit + 1)
        ).all()
    )
    return rows[:limit], total, len(rows) > limit


def agent_run_status_counts(session: Session) -> dict[str, int]:
    rows = session.execute(select(AgentRun.status, func.count()).group_by(AgentRun.status)).all()
    return {str(status): int(count) for status, count in rows}


def count_pending_agent_run_approvals(session: Session) -> int:
    return int(
        session.scalar(select(func.count()).select_from(AgentRunApproval).where(AgentRunApproval.status == "pending"))
        or 0
    )


def count_recent_failed_agent_runs(session: Session, *, since: datetime) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.status == "failed", AgentRun.finished_at >= since)
        )
        or 0
    )


def get_agent_run_by_idempotency_key(
    session: Session,
    *,
    workflow_key: str,
    idempotency_key: str,
) -> AgentRun | None:
    return (
        session.query(AgentRun)
        .filter(
            AgentRun.workflow_key == workflow_key,
            AgentRun.idempotency_key == idempotency_key,
        )
        .first()
    )


def _agent_run_is_available(now: datetime):
    pending_wait = func.json_extract(AgentRun.input_payload, "$.pending_wait")
    resume_value = func.json_extract(AgentRun.input_payload, "$.resume_value")
    return or_(
        resume_value.is_not(None),
        AgentRun.available_at <= now,
        and_(AgentRun.available_at.is_(None), pending_wait.is_(None)),
    )


def list_claimable_agent_runs(
    session: Session,
    *,
    now: datetime,
    limit: int = 50,
) -> list[AgentRun]:
    return list(
        session.query(AgentRun)
        .filter(
            AgentRun.status == "queued",
            _agent_run_is_available(now),
            or_(AgentRun.lease_expires_at.is_(None), AgentRun.lease_expires_at <= now),
            AgentRun.attempt_count < AgentRun.max_attempts,
        )
        .order_by(AgentRun.created_at.asc(), AgentRun.id.asc())
        .limit(limit)
        .all()
    )


def claim_agent_run(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
) -> AgentRun | None:
    ensure_legal_run_transition("queued", "running")
    lease_expires_at = now + timedelta(seconds=max(1, lease_seconds))
    result = session.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status == "queued",
            _agent_run_is_available(now),
            or_(AgentRun.lease_expires_at.is_(None), AgentRun.lease_expires_at <= now),
            AgentRun.attempt_count < AgentRun.max_attempts,
        )
        .values(
            status="running",
            lease_owner=worker_id,
            lease_expires_at=lease_expires_at,
            heartbeat_at=now,
            attempt_count=AgentRun.attempt_count + 1,
            started_at=func.coalesce(AgentRun.started_at, now),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return None
    return session.get(AgentRun, run_id, populate_existing=True)


def heartbeat_agent_run(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    reject_cancel_requested: bool = False,
) -> bool:
    conditions = [
        AgentRun.id == run_id,
        AgentRun.status == "running",
        AgentRun.lease_owner == worker_id,
    ]
    if reject_cancel_requested:
        conditions.append(AgentRun.cancel_requested_at.is_(None))
    result = session.execute(
        update(AgentRun)
        .where(*conditions)
        .values(
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=max(1, lease_seconds)),
        )
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def release_agent_run_lease(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
) -> bool:
    result = session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.lease_owner == worker_id)
        .values(lease_owner=None, lease_expires_at=None, heartbeat_at=None)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def recover_expired_agent_runs(session: Session, *, now: datetime) -> int:
    candidates = list(
        session.query(AgentRun)
        .filter(
            AgentRun.status == "running",
            or_(
                AgentRun.lease_owner.is_(None),
                AgentRun.lease_expires_at.is_(None),
                AgentRun.lease_expires_at <= now,
            ),
        )
        .order_by(AgentRun.created_at.asc(), AgentRun.id.asc())
        .all()
    )
    recovered = 0
    for candidate in candidates:
        conditions = (
            AgentRun.id == candidate.id,
            AgentRun.status == "running",
            or_(
                AgentRun.lease_owner.is_(None),
                AgentRun.lease_expires_at.is_(None),
                AgentRun.lease_expires_at <= now,
            ),
        )
        common_values: dict[str, Any] = {
            "lease_owner": None,
            "lease_expires_at": None,
            "heartbeat_at": None,
        }
        if candidate.cancel_requested_at is not None:
            target_status = "cancelled"
            values = {
                **common_values,
                "status": "cancelled",
                "finished_at": now,
            }
        elif candidate.attempt_count >= candidate.max_attempts:
            target_status = "failed"
            values = {
                **common_values,
                "status": "failed",
                "finished_at": now,
                "error_code": "WorkerLeaseExpired",
                "error_message": "Agent run exhausted its worker lease attempts",
            }
        else:
            target_status = "queued"
            values = {
                **common_values,
                "status": "queued",
                "available_at": now,
            }
        ensure_legal_run_transition(candidate.status, target_status)
        result = session.execute(
            update(AgentRun).where(*conditions).values(**values).execution_options(synchronize_session=False)
        )
        updated = int(result.rowcount or 0)
        recovered += updated
        if updated:
            session.expire(candidate)
    return recovered


def get_agent_run(session: Session, run_id: str) -> AgentRun | None:
    return session.get(AgentRun, run_id)


def list_agent_run_steps(session: Session, *, run_id: str) -> list[AgentRunStep]:
    return list(
        session.query(AgentRunStep).filter(AgentRunStep.run_id == run_id).order_by(AgentRunStep.sequence_no.asc()).all()
    )


def list_pending_approvals(session: Session, *, limit: int = 100) -> list[AgentRunApproval]:
    return list(
        session.query(AgentRunApproval)
        .filter(AgentRunApproval.status == "pending")
        .order_by(AgentRunApproval.created_at.asc())
        .limit(limit)
        .all()
    )


def get_approval(session: Session, approval_id: str) -> AgentRunApproval | None:
    return session.get(AgentRunApproval, approval_id)


def resolve_pending_approval(
    session: Session,
    *,
    approval_id: str,
    status: str,
    response_payload: dict[str, Any],
    resolved_by_type: str,
    resolved_by_id: str,
    resolved_at: datetime,
) -> AgentRunApproval | None:
    awaiting_run_ids = select(AgentRun.id).where(AgentRun.status == "awaiting_approval")
    result = session.execute(
        update(AgentRunApproval)
        .where(
            AgentRunApproval.id == approval_id,
            AgentRunApproval.status == "pending",
            AgentRunApproval.run_id.in_(awaiting_run_ids),
        )
        .values(
            status=status,
            response_payload=protect_sensitive_data(
                response_payload,
                purpose="automation-runtime-state",
            ),
            resolved_by_type=resolved_by_type,
            resolved_by_id=resolved_by_id,
            resolved_at=resolved_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return None
    return session.get(AgentRunApproval, approval_id, populate_existing=True)


def list_webhook_subscriptions(session: Session, *, limit: int = 100) -> list[WebhookSubscription]:
    return list(session.query(WebhookSubscription).order_by(WebhookSubscription.created_at.desc()).limit(limit).all())


def get_webhook_subscription(session: Session, subscription_id: str) -> WebhookSubscription | None:
    return session.get(WebhookSubscription, subscription_id)


def create_webhook_subscription(session: Session, **kwargs) -> WebhookSubscription:
    item = WebhookSubscription(**kwargs)
    session.add(item)
    return item


def delete_webhook_subscription(session: Session, subscription: WebhookSubscription) -> None:
    session.delete(subscription)


def list_active_webhook_subscriptions(session: Session, *, event_type: str) -> list[WebhookSubscription]:
    return list(session.query(WebhookSubscription).filter(WebhookSubscription.status == "active").all())


def create_webhook_delivery(
    session: Session,
    *,
    subscription: WebhookSubscription,
    event: AutomationEvent,
) -> WebhookDelivery:
    delivery = WebhookDelivery(
        subscription_id=subscription.id,
        event_type=event.event_type,
        event_id=event.event_id,
        status="pending",
        target_url=subscription.target_url,
        payload=protect_sensitive_data(event.model_dump(), purpose="automation-webhook-payload"),
        headers=subscription.headers,
        next_attempt_at=shanghai_now(),
    )
    session.add(delivery)
    return delivery


def list_due_webhook_deliveries(session: Session, *, now: datetime, limit: int = 50) -> list[WebhookDelivery]:
    return list(
        session.query(WebhookDelivery)
        .filter(
            WebhookDelivery.status.in_(["pending", "retry_scheduled"]),
            WebhookDelivery.next_attempt_at <= now,
        )
        .order_by(WebhookDelivery.next_attempt_at.asc())
        .limit(limit)
        .all()
    )


def list_webhook_deliveries(session: Session, *, limit: int = 200) -> list[WebhookDelivery]:
    return list(session.query(WebhookDelivery).order_by(WebhookDelivery.created_at.desc()).limit(limit).all())


def get_webhook_delivery(session: Session, delivery_id: str) -> WebhookDelivery | None:
    return session.get(WebhookDelivery, delivery_id)


def list_webhook_dead_letters(session: Session, *, limit: int = 200) -> list[WebhookDeadLetter]:
    return list(session.query(WebhookDeadLetter).order_by(WebhookDeadLetter.created_at.desc()).limit(limit).all())


def get_webhook_dead_letter(session: Session, dead_letter_id: str) -> WebhookDeadLetter | None:
    return session.get(WebhookDeadLetter, dead_letter_id)


def delete_webhook_dead_letter(session: Session, dead_letter: WebhookDeadLetter) -> None:
    session.delete(dead_letter)


def create_dead_letter(
    session: Session,
    *,
    delivery: WebhookDelivery,
    reason: str,
) -> WebhookDeadLetter:
    dead = WebhookDeadLetter(
        delivery_id=delivery.id,
        subscription_id=delivery.subscription_id,
        event_type=delivery.event_type,
        event_id=delivery.event_id,
        reason=reason,
        payload=delivery.payload,
        last_response_status=delivery.last_response_status,
        last_error=delivery.last_error,
    )
    session.add(dead)
    return dead

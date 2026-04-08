from __future__ import annotations

from datetime import datetime
from typing import Any

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
) -> AgentRun:
    run = AgentRun(
        workflow_key=workflow_key,
        trigger_kind=trigger_kind,
        trigger_event=trigger_event,
        target_type=target_type,
        target_id=target_id,
        thread_id=thread_id,
        input_payload=input_payload or {},
        context_payload=context_payload or {},
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
        payload=payload or {},
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
        input_payload=input_payload or {},
        output_payload=output_payload or {},
        error_payload=error_payload or {},
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
        request_payload=request_payload or {},
    )
    session.add(approval)
    return approval


def list_agent_runs(session: Session, *, limit: int = 50) -> list[AgentRun]:
    return list(session.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit).all())


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
        payload=event.model_dump(),
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

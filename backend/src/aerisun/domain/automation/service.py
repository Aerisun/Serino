from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation.models import AgentRun, AutomationEvent, WebhookDelivery
from aerisun.domain.automation.runtime import AutomationRuntime
from aerisun.domain.automation.schemas import (
    AgentRunApprovalRead,
    AgentRunRead,
    AgentRunStepRead,
    ApprovalDecisionWrite,
    WebhookDeadLetterRead,
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
)
from aerisun.domain.exceptions import ResourceNotFound


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
        thread_id=__import__("uuid").uuid4().hex,
    )
    session.commit()
    session.refresh(run)
    return AgentRunRead.model_validate(run)


def list_runs(session: Session) -> list[AgentRunRead]:
    return [AgentRunRead.model_validate(item) for item in repo.list_agent_runs(session)]


def get_run_detail(session: Session, run_id: str) -> tuple[AgentRunRead, list[AgentRunStepRead]]:
    run = repo.get_agent_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    steps = repo.list_agent_run_steps(session, run_id=run_id)
    return AgentRunRead.model_validate(run), [AgentRunStepRead.model_validate(step) for step in steps]


def list_pending_approvals(session: Session) -> list[AgentRunApprovalRead]:
    return [AgentRunApprovalRead.model_validate(item) for item in repo.list_pending_approvals(session)]


def list_webhook_subscriptions(session: Session) -> list[WebhookSubscriptionRead]:
    return [WebhookSubscriptionRead.model_validate(item) for item in repo.list_webhook_subscriptions(session)]


def create_webhook_subscription(session: Session, payload: WebhookSubscriptionCreate) -> WebhookSubscriptionRead:
    item = repo.create_webhook_subscription(
        session,
        name=payload.name,
        status=payload.status,
        target_url=payload.target_url,
        secret=payload.secret,
        event_types=payload.event_types,
        timeout_seconds=payload.timeout_seconds,
        max_attempts=payload.max_attempts,
        headers=payload.headers,
    )
    session.commit()
    session.refresh(item)
    return WebhookSubscriptionRead.model_validate(item)


def update_webhook_subscription(
    session: Session,
    *,
    subscription_id: str,
    payload: WebhookSubscriptionUpdate,
) -> WebhookSubscriptionRead:
    item = repo.get_webhook_subscription(session, subscription_id)
    if item is None:
        raise ResourceNotFound("Webhook subscription not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)
    session.commit()
    session.refresh(item)
    return WebhookSubscriptionRead.model_validate(item)


def delete_webhook_subscription(session: Session, *, subscription_id: str) -> None:
    item = repo.get_webhook_subscription(session, subscription_id)
    if item is None:
        raise ResourceNotFound("Webhook subscription not found")
    repo.delete_webhook_subscription(session, item)
    session.commit()


def list_webhook_deliveries(session: Session) -> list[WebhookDeliveryRead]:
    return [WebhookDeliveryRead.model_validate(item) for item in repo.list_webhook_deliveries(session)]


def list_webhook_dead_letters(session: Session) -> list[WebhookDeadLetterRead]:
    return [WebhookDeadLetterRead.model_validate(item) for item in repo.list_webhook_dead_letters(session)]


def replay_dead_letter(session: Session, *, dead_letter_id: str) -> WebhookDeliveryRead:
    dead_letter = repo.get_webhook_dead_letter(session, dead_letter_id)
    if dead_letter is None:
        raise ResourceNotFound("Webhook dead letter not found")
    subscription = repo.get_webhook_subscription(session, dead_letter.subscription_id)
    if subscription is None:
        raise ResourceNotFound("Webhook subscription not found")
    delivery = repo.create_webhook_delivery(
        session,
        subscription=subscription,
        event=AutomationEvent(
            event_type=dead_letter.event_type,
            event_id=dead_letter.event_id,
            target_type=str(dead_letter.payload.get("target_type") or "unknown"),
            target_id=str(dead_letter.payload.get("target_id") or "unknown"),
            payload=dict(dead_letter.payload),
        ),
    )
    repo.delete_webhook_dead_letter(session, dead_letter)
    session.commit()
    session.refresh(delivery)
    return WebhookDeliveryRead.model_validate(delivery)


def trigger_delivery_retry(session: Session, *, delivery_id: str) -> WebhookDeliveryRead:
    delivery = repo.get_webhook_delivery(session, delivery_id)
    if delivery is None:
        raise ResourceNotFound("Webhook delivery not found")
    delivery.status = "pending"
    delivery.next_attempt_at = datetime.now(UTC)
    session.commit()
    session.refresh(delivery)
    return WebhookDeliveryRead.model_validate(delivery)


def execute_due_runs(session: Session, runtime: AutomationRuntime) -> int:
    runs = [item for item in repo.list_agent_runs(session, limit=20) if item.status == "queued"]
    processed = 0
    for run in runs:
        processed += 1
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        session.commit()
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=1,
            node_key="workflow_dispatch",
            step_kind="node_entered",
            status="running",
            narrative=f"开始执行工作流 {run.workflow_key}。",
            input_payload=run.input_payload,
            started_at=datetime.now(UTC),
        )
        session.commit()
        result = runtime.invoke(
            {
                "run_id": run.id,
                "target_type": run.target_type,
                "target_id": run.target_id,
                "trigger_event": run.trigger_event,
                "context_payload": run.context_payload,
            },
            thread_id=run.thread_id,
        )
        snapshot = runtime.get_state(thread_id=run.thread_id)
        run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
        run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            run.status = "awaiting_approval"
            repo.add_agent_run_step(
                session,
                run_id=run.id,
                sequence_no=2,
                node_key="request_approval",
                step_kind="interrupt_requested",
                status="interrupted",
                narrative="工作流请求人工审批。",
                output_payload={"interrupt_count": len(interrupts)},
                finished_at=datetime.now(UTC),
            )
            first = interrupts[0]
            interrupt_id = getattr(first, "id", None) or f"{run.id}:approval"
            request_payload = {"value": getattr(first, "value", None)}
            repo.create_agent_run_approval(
                session,
                run_id=run.id,
                step_id=None,
                interrupt_id=interrupt_id,
                node_key="request_approval",
                approval_type="moderation_decision",
                request_payload=request_payload,
            )
        else:
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            run.result_payload = result
            repo.add_agent_run_step(
                session,
                run_id=run.id,
                sequence_no=2,
                node_key="apply_decision",
                step_kind="node_completed",
                status="completed",
                narrative="工作流已完成。",
                output_payload=result,
                finished_at=datetime.now(UTC),
            )
        session.commit()
    return processed


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
    approval.resolved_at = datetime.now(UTC)
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=len(repo.list_agent_run_steps(session, run_id=run.id)) + 1,
        node_key="request_approval",
        step_kind="resume_requested",
        status="running",
        narrative="管理员已提交审批结果，准备恢复工作流。",
        input_payload=decision_payload,
        started_at=datetime.now(UTC),
    )
    session.commit()

    result = runtime.resume(thread_id=run.thread_id, resume_value=decision_payload)
    snapshot = runtime.get_state(thread_id=run.thread_id)
    run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
    run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
    run.result_payload = result
    run.status = "completed"
    run.finished_at = datetime.now(UTC)
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=len(repo.list_agent_run_steps(session, run_id=run.id)) + 1,
        node_key="apply_decision",
        step_kind="node_completed",
        status="completed",
        narrative="审批结果已应用，工作流完成。",
        output_payload=result,
        finished_at=datetime.now(UTC),
    )
    session.commit()
    session.refresh(run)
    return AgentRunRead.model_validate(run)


def emit_event(session: Session, event: AutomationEvent) -> None:
    subscriptions = repo.list_active_webhook_subscriptions(session, event_type=event.event_type)
    for subscription in subscriptions:
        if subscription.event_types and event.event_type not in subscription.event_types:
            continue
        repo.create_webhook_delivery(session, subscription=subscription, event=event)
    session.commit()


def dispatch_due_webhooks(session: Session) -> int:
    now = datetime.now(UTC)
    deliveries = repo.list_due_webhook_deliveries(session, now=now)
    processed = 0
    for delivery in deliveries:
        processed += 1
        _deliver_once(session, delivery, now=now)
    return processed


def _deliver_once(session: Session, delivery: WebhookDelivery, *, now: datetime) -> None:
    settings = get_settings()
    delivery.status = "delivering"
    delivery.last_attempt_at = now
    delivery.attempt_count += 1
    session.commit()
    timeout = httpx.Timeout(10.0)
    try:
        response = httpx.post(delivery.target_url, json=delivery.payload, headers=delivery.headers, timeout=timeout)
        delivery.last_response_status = response.status_code
        delivery.last_response_body = response.text[:2000]
        if response.status_code < 400:
            delivery.status = "succeeded"
            delivery.delivered_at = datetime.now(UTC)
        elif response.status_code in {408, 409, 429} or response.status_code >= 500:
            _schedule_retry_or_dead_letter(session, delivery, reason=f"http_{response.status_code}")
            return
        else:
            delivery.status = "dead_lettered"
            delivery.last_error = f"Non-retryable HTTP {response.status_code}"
            repo.create_dead_letter(session, delivery=delivery, reason=f"http_{response.status_code}")
        session.commit()
    except httpx.HTTPError as exc:
        delivery.last_error = str(exc)
        _schedule_retry_or_dead_letter(session, delivery, reason="network_error")


def _schedule_retry_or_dead_letter(session: Session, delivery: WebhookDelivery, *, reason: str) -> None:
    max_attempts = 6
    if delivery.attempt_count >= max_attempts:
        delivery.status = "dead_lettered"
        repo.create_dead_letter(session, delivery=delivery, reason=reason)
        session.commit()
        return
    backoff = min(30 * (4 ** max(delivery.attempt_count - 1, 0)), 7200)
    delivery.status = "retry_scheduled"
    delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
    session.commit()

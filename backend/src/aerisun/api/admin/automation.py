from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
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
from aerisun.domain.automation.service import (
    create_webhook_subscription,
    delete_webhook_subscription,
    get_run_detail,
    list_pending_approvals,
    list_runs,
    list_webhook_dead_letters,
    list_webhook_deliveries,
    list_webhook_subscriptions,
    replay_dead_letter,
    resolve_approval,
    trigger_delivery_retry,
    update_webhook_subscription,
)
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin

router = APIRouter(prefix="/automation", tags=["admin-automation"])


@router.get("/runs", response_model=list[AgentRunRead], summary="获取 Agent 运行记录")
def get_runs(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentRunRead]:
    return list_runs(session)


@router.get("/runs/{run_id}", response_model=AgentRunRead, summary="获取单个 Agent 运行记录")
def get_run(
    run_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunRead:
    run, _steps = get_run_detail(session, run_id)
    return run


@router.get("/runs/{run_id}/steps", response_model=list[AgentRunStepRead], summary="获取运行步骤")
def get_run_steps(
    run_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentRunStepRead]:
    _run, steps = get_run_detail(session, run_id)
    return steps


@router.get("/approvals", response_model=list[AgentRunApprovalRead], summary="获取待审批项目")
def get_approvals(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentRunApprovalRead]:
    return list_pending_approvals(session)


@router.post(
    "/approvals/{approval_id}/decision",
    response_model=AgentRunRead,
    status_code=status.HTTP_200_OK,
    summary="提交审批结果并恢复工作流",
)
def post_approval_decision(
    approval_id: str,
    payload: ApprovalDecisionWrite,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunRead:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    return resolve_approval(
        session,
        get_automation_runtime(),
        approval_id=approval_id,
        actor_id=admin.id,
        decision_payload=payload,
    )


@router.get("/webhooks", response_model=list[WebhookSubscriptionRead], summary="获取 Webhook 订阅")
def get_webhooks(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[WebhookSubscriptionRead]:
    return list_webhook_subscriptions(session)


@router.post(
    "/webhooks",
    response_model=WebhookSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Webhook 订阅",
)
def post_webhook(
    payload: WebhookSubscriptionCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookSubscriptionRead:
    return create_webhook_subscription(session, payload)


@router.put("/webhooks/{subscription_id}", response_model=WebhookSubscriptionRead, summary="更新 Webhook 订阅")
def put_webhook(
    subscription_id: str,
    payload: WebhookSubscriptionUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookSubscriptionRead:
    return update_webhook_subscription(session, subscription_id=subscription_id, payload=payload)


@router.delete("/webhooks/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 Webhook 订阅")
def delete_webhook(
    subscription_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    delete_webhook_subscription(session, subscription_id=subscription_id)


@router.get("/deliveries", response_model=list[WebhookDeliveryRead], summary="获取 Webhook 投递记录")
def get_deliveries(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[WebhookDeliveryRead]:
    return list_webhook_deliveries(session)


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryRead, summary="重试 Webhook 投递")
def post_delivery_retry(
    delivery_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookDeliveryRead:
    return trigger_delivery_retry(session, delivery_id=delivery_id)


@router.get("/dead-letters", response_model=list[WebhookDeadLetterRead], summary="获取 Webhook 死信列表")
def get_dead_letters(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[WebhookDeadLetterRead]:
    return list_webhook_dead_letters(session)


@router.post("/dead-letters/{dead_letter_id}/replay", response_model=WebhookDeliveryRead, summary="回放死信投递")
def post_dead_letter_replay(
    dead_letter_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookDeliveryRead:
    return replay_dead_letter(session, dead_letter_id=dead_letter_id)

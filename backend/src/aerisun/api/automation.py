from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Query
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.automation.runtime_registry import get_automation_runtime
from aerisun.domain.automation.schemas import AgentWorkflowWebhookTriggerRead
from aerisun.domain.automation.service import trigger_webhook_workflow

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])


@router.post(
    "/webhook-triggers/{workflow_key}/{binding_id}",
    response_model=AgentWorkflowWebhookTriggerRead,
    summary="触发工作流 Webhook 绑定",
)
def post_workflow_webhook_trigger(
    workflow_key: str,
    binding_id: str,
    body: dict[str, Any] | None = Body(default=None),
    token: str | None = Query(default=None),
    x_workflow_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> AgentWorkflowWebhookTriggerRead:
    return trigger_webhook_workflow(
        session,
        get_automation_runtime(),
        workflow_key=workflow_key,
        binding_id=binding_id,
        provided_secret=str(token or x_workflow_token or ""),
        body=body,
    )

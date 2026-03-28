from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class ApprovalDecisionWrite(BaseModel):
    action: str = Field(default="approve")
    reason: str | None = None


class AgentModelConfigRead(ModelBase):
    enabled: bool = False
    provider: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout_seconds: int = Field(default=20, ge=5, le=300)
    advisory_prompt: str = ""
    is_ready: bool = False


class AgentModelConfigUpdate(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    advisory_prompt: str | None = None


class AgentModelConfigTestRead(ModelBase):
    ok: bool = True
    model: str
    endpoint: str
    summary: str


class AgentWorkflowDraftMessageRead(ModelBase):
    role: str
    content: str
    created_at: datetime


class AgentWorkflowDraftOptionRead(ModelBase):
    label: str
    value: str
    description: str = ""
    requires_input: bool = False


class AgentWorkflowDraftQuestionRead(ModelBase):
    key: str = ""
    prompt: str
    options: list[AgentWorkflowDraftOptionRead] = Field(default_factory=list)


class AgentWorkflowDraftRead(ModelBase):
    id: str = "global"
    status: str = "active"
    summary: str = ""
    ready_to_create: bool = False
    suggested_template: str | None = None
    questions: list[AgentWorkflowDraftQuestionRead] = Field(default_factory=list)
    current_question: str = ""
    options: list[AgentWorkflowDraftOptionRead] = Field(default_factory=list)
    working_document: str = ""
    messages: list[AgentWorkflowDraftMessageRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentWorkflowDraftChatWrite(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AgentWorkflowDraftCreateWrite(BaseModel):
    force: bool = False


class AgentWorkflowDraftCreateRead(ModelBase):
    ok: bool = True
    summary: str
    draft_cleared: bool = True
    workflow: "AgentWorkflowRead"


class AgentWorkflowCreate(BaseModel):
    key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    trigger_event: str = Field(min_length=1, max_length=120)
    target_type: str | None = Field(default=None, max_length=80)
    enabled: bool = True
    require_human_approval: bool = True
    instructions: str = Field(default="", max_length=4000)


class AgentWorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    trigger_event: str | None = Field(default=None, min_length=1, max_length=120)
    target_type: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    require_human_approval: bool | None = None
    instructions: str | None = Field(default=None, max_length=4000)


class AgentWorkflowRead(ModelBase):
    key: str
    name: str
    description: str
    trigger_event: str
    target_type: str | None = None
    enabled: bool = True
    require_human_approval: bool = True
    instructions: str = ""
    built_in: bool = False


class WebhookSubscriptionCreate(BaseModel):
    name: str
    target_url: str
    event_types: list[str] = Field(default_factory=list)
    secret: str | None = None
    timeout_seconds: int = 10
    max_attempts: int = 6
    status: str = "active"
    headers: dict[str, Any] = Field(default_factory=dict)


class WebhookSubscriptionUpdate(BaseModel):
    name: str | None = None
    target_url: str | None = None
    event_types: list[str] | None = None
    secret: str | None = None
    timeout_seconds: int | None = None
    max_attempts: int | None = None
    status: str | None = None
    headers: dict[str, Any] | None = None


class TelegramWebhookConnectWrite(BaseModel):
    bot_token: str = Field(min_length=10, max_length=256)
    send_test_message: bool = True


class TelegramWebhookConnectRead(ModelBase):
    ok: bool = False
    status: str
    summary: str
    bot_username: str | None = None
    chat_id: int | str | None = None
    target_url: str | None = None


class AgentRunRead(ModelBase):
    id: str
    workflow_key: str
    status: str
    trigger_kind: str
    trigger_event: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    thread_id: str
    latest_checkpoint_id: str | None = None
    checkpoint_ns: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    context_payload: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunStepRead(ModelBase):
    id: str
    run_id: str
    sequence_no: int
    node_key: str
    step_kind: str
    status: str
    narrative: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_payload: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunApprovalRead(ModelBase):
    id: str
    run_id: str
    step_id: str | None = None
    interrupt_id: str
    node_key: str
    approval_type: str
    status: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    requested_by_type: str
    resolved_by_type: str | None = None
    resolved_by_id: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunCollectionRead(BaseModel):
    items: list[AgentRunRead] = Field(default_factory=list)


class WebhookSubscriptionRead(ModelBase):
    id: str
    name: str
    status: str
    target_url: str
    secret: str | None = None
    event_types: list[str] = Field(default_factory=list)
    timeout_seconds: int
    max_attempts: int
    backoff_policy: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    last_delivery_at: datetime | None = None
    last_success_at: datetime | None = None
    last_test_status: str | None = None
    last_test_error: str | None = None
    last_tested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryRead(ModelBase):
    id: str
    subscription_id: str
    event_type: str
    event_id: str
    status: str
    target_url: str
    payload: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_response_status: int | None = None
    last_response_body: str | None = None
    last_error: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookDeadLetterRead(ModelBase):
    id: str
    delivery_id: str
    subscription_id: str
    event_type: str
    event_id: str
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)
    last_response_status: int | None = None
    last_error: str | None = None
    dead_lettered_at: datetime
    created_at: datetime
    updated_at: datetime

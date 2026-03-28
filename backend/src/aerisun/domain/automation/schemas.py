from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class ApprovalDecisionWrite(BaseModel):
    action: str = Field(default="approve")
    reason: str | None = None


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

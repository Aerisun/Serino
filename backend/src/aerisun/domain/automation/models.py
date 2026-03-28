from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


AutomationStatus = Literal[
    "queued",
    "running",
    "awaiting_approval",
    "interrupted",
    "completed",
    "failed",
    "cancelled",
]

WebhookDeliveryStatus = Literal[
    "pending",
    "delivering",
    "succeeded",
    "retry_scheduled",
    "failed",
    "dead_lettered",
]


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_status_created_at", "status", "created_at"),
        Index("ix_agent_runs_target", "target_type", "target_id"),
        Index("ix_agent_runs_workflow_key_created_at", "workflow_key", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workflow_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    trigger_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="event")
    trigger_event: Mapped[str | None] = mapped_column(String(120))
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(64))
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    latest_checkpoint_id: Mapped[str | None] = mapped_column(String(120))
    checkpoint_ns: Mapped[str | None] = mapped_column(String(120))
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    context_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunStep(Base, TimestampMixin):
    __tablename__ = "agent_run_steps"
    __table_args__ = (
        Index("ix_agent_run_steps_run_id_sequence_no", "run_id", "sequence_no"),
        Index("ix_agent_run_steps_run_id_status", "run_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    node_key: Mapped[str] = mapped_column(String(120), nullable=False)
    step_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunApproval(Base, TimestampMixin):
    __tablename__ = "agent_run_approvals"
    __table_args__ = (
        Index("ix_agent_run_approvals_run_id_status", "run_id", "status"),
        Index("ix_agent_run_approvals_interrupt_id", "interrupt_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(36))
    interrupt_id: Mapped[str] = mapped_column(String(120), nullable=False)
    node_key: Mapped[str] = mapped_column(String(120), nullable=False)
    approval_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    requested_by_type: Mapped[str] = mapped_column(String(40), nullable=False, default="system")
    resolved_by_type: Mapped[str | None] = mapped_column(String(40))
    resolved_by_id: Mapped[str | None] = mapped_column(String(36))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookSubscription(Base, TimestampMixin):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (Index("ix_webhook_subscriptions_status_created_at", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str | None] = mapped_column(String(255))
    event_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    backoff_policy: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {"initial_seconds": 30, "multiplier": 4, "max_seconds": 7200},
        nullable=False,
    )
    headers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDelivery(Base, TimestampMixin):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_status_next_attempt_at", "status", "next_attempt_at"),
        Index("ix_webhook_deliveries_subscription_id", "subscription_id"),
        Index("ix_webhook_deliveries_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    headers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_response_status: Mapped[int | None] = mapped_column(Integer)
    last_response_body: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDeadLetter(Base, TimestampMixin):
    __tablename__ = "webhook_dead_letters"
    __table_args__ = (
        Index("ix_webhook_dead_letters_subscription_id", "subscription_id"),
        Index("ix_webhook_dead_letters_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    delivery_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_response_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    dead_lettered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


@dataclass(slots=True)
class AutomationEvent:
    event_type: str
    event_id: str
    target_type: str
    target_id: str
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

"""Add automation runtime & webhook tables.

Revision ID: 0025_add_automation_tables
Revises: 0023_add_site_icon_url
Create Date: 2026-03-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0025_add_automation_tables"
down_revision = "0023_add_site_icon_url"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "agent_runs" not in existing_tables:
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workflow_key", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("trigger_kind", sa.String(length=40), nullable=False, server_default="event"),
            sa.Column("trigger_event", sa.String(length=120)),
            sa.Column("target_type", sa.String(length=80)),
            sa.Column("target_id", sa.String(length=64)),
            sa.Column("thread_id", sa.String(length=64), nullable=False),
            sa.Column("latest_checkpoint_id", sa.String(length=120)),
            sa.Column("checkpoint_ns", sa.String(length=120)),
            sa.Column("input_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("context_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("result_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("error_code", sa.String(length=80)),
            sa.Column("error_message", sa.Text()),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("thread_id", name="uq_agent_runs_thread_id"),
        )
        existing_tables.add("agent_runs")

    if not _has_index(inspector, "agent_runs", "ix_agent_runs_status_created_at"):
        op.create_index("ix_agent_runs_status_created_at", "agent_runs", ["status", "created_at"])
    if not _has_index(inspector, "agent_runs", "ix_agent_runs_target"):
        op.create_index("ix_agent_runs_target", "agent_runs", ["target_type", "target_id"])
    if not _has_index(inspector, "agent_runs", "ix_agent_runs_workflow_key_created_at"):
        op.create_index("ix_agent_runs_workflow_key_created_at", "agent_runs", ["workflow_key", "created_at"])

    if "agent_run_steps" not in existing_tables:
        op.create_table(
            "agent_run_steps",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("sequence_no", sa.Integer(), nullable=False),
            sa.Column("node_key", sa.String(length=120), nullable=False),
            sa.Column("step_kind", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
            sa.Column("narrative", sa.Text(), nullable=False, server_default=""),
            sa.Column("input_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("output_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("error_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        existing_tables.add("agent_run_steps")

    if not _has_index(inspector, "agent_run_steps", "ix_agent_run_steps_run_id_sequence_no"):
        op.create_index("ix_agent_run_steps_run_id_sequence_no", "agent_run_steps", ["run_id", "sequence_no"])
    if not _has_index(inspector, "agent_run_steps", "ix_agent_run_steps_run_id_status"):
        op.create_index("ix_agent_run_steps_run_id_status", "agent_run_steps", ["run_id", "status"])

    if "agent_run_approvals" not in existing_tables:
        op.create_table(
            "agent_run_approvals",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("step_id", sa.String(length=36)),
            sa.Column("interrupt_id", sa.String(length=120), nullable=False),
            sa.Column("node_key", sa.String(length=120), nullable=False),
            sa.Column("approval_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("request_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("response_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("requested_by_type", sa.String(length=40), nullable=False, server_default="system"),
            sa.Column("resolved_by_type", sa.String(length=40)),
            sa.Column("resolved_by_id", sa.String(length=36)),
            sa.Column("resolved_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        existing_tables.add("agent_run_approvals")

    if not _has_index(inspector, "agent_run_approvals", "ix_agent_run_approvals_run_id_status"):
        op.create_index("ix_agent_run_approvals_run_id_status", "agent_run_approvals", ["run_id", "status"])
    if not _has_index(inspector, "agent_run_approvals", "ix_agent_run_approvals_interrupt_id"):
        op.create_index("ix_agent_run_approvals_interrupt_id", "agent_run_approvals", ["interrupt_id"])

    if "webhook_subscriptions" not in existing_tables:
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("target_url", sa.String(length=500), nullable=False),
            sa.Column("secret", sa.String(length=255)),
            sa.Column("event_types", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="6"),
            sa.Column(
                "backoff_policy",
                sa.JSON(),
                nullable=False,
                server_default=sa.text('\'{"initial_seconds":30,"multiplier":4,"max_seconds":7200}\''),
            ),
            sa.Column("headers", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("last_delivery_at", sa.DateTime(timezone=True)),
            sa.Column("last_success_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        existing_tables.add("webhook_subscriptions")

    if not _has_index(inspector, "webhook_subscriptions", "ix_webhook_subscriptions_status_created_at"):
        op.create_index(
            "ix_webhook_subscriptions_status_created_at",
            "webhook_subscriptions",
            ["status", "created_at"],
        )

    if "webhook_deliveries" not in existing_tables:
        op.create_table(
            "webhook_deliveries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("subscription_id", sa.String(length=36), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("target_url", sa.String(length=500), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("headers", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
            sa.Column("last_response_status", sa.Integer()),
            sa.Column("last_response_body", sa.Text()),
            sa.Column("last_error", sa.Text()),
            sa.Column("delivered_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        existing_tables.add("webhook_deliveries")

    if not _has_index(inspector, "webhook_deliveries", "ix_webhook_deliveries_status_next_attempt_at"):
        op.create_index(
            "ix_webhook_deliveries_status_next_attempt_at",
            "webhook_deliveries",
            ["status", "next_attempt_at"],
        )
    if not _has_index(inspector, "webhook_deliveries", "ix_webhook_deliveries_subscription_id"):
        op.create_index("ix_webhook_deliveries_subscription_id", "webhook_deliveries", ["subscription_id"])
    if not _has_index(inspector, "webhook_deliveries", "ix_webhook_deliveries_event_type"):
        op.create_index("ix_webhook_deliveries_event_type", "webhook_deliveries", ["event_type"])

    if "webhook_dead_letters" not in existing_tables:
        op.create_table(
            "webhook_dead_letters",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("delivery_id", sa.String(length=36), nullable=False),
            sa.Column("subscription_id", sa.String(length=36), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("reason", sa.String(length=120), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("last_response_status", sa.Integer()),
            sa.Column("last_error", sa.Text()),
            sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("delivery_id", name="uq_webhook_dead_letters_delivery_id"),
        )

    if not _has_index(inspector, "webhook_dead_letters", "ix_webhook_dead_letters_subscription_id"):
        op.create_index("ix_webhook_dead_letters_subscription_id", "webhook_dead_letters", ["subscription_id"])
    if not _has_index(inspector, "webhook_dead_letters", "ix_webhook_dead_letters_event_type"):
        op.create_index("ix_webhook_dead_letters_event_type", "webhook_dead_letters", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_webhook_dead_letters_event_type", table_name="webhook_dead_letters")
    op.drop_index("ix_webhook_dead_letters_subscription_id", table_name="webhook_dead_letters")
    op.drop_table("webhook_dead_letters")

    op.drop_index("ix_webhook_deliveries_event_type", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_subscription_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status_next_attempt_at", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("ix_webhook_subscriptions_status_created_at", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")

    op.drop_index("ix_agent_run_approvals_interrupt_id", table_name="agent_run_approvals")
    op.drop_index("ix_agent_run_approvals_run_id_status", table_name="agent_run_approvals")
    op.drop_table("agent_run_approvals")

    op.drop_index("ix_agent_run_steps_run_id_status", table_name="agent_run_steps")
    op.drop_index("ix_agent_run_steps_run_id_sequence_no", table_name="agent_run_steps")
    op.drop_table("agent_run_steps")

    op.drop_index("ix_agent_runs_workflow_key_created_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_target", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")

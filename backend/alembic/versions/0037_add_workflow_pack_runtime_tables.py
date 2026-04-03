"""Add workflow gate and build task tables.

Revision ID: 0037_add_workflow_pack_runtime_tables
Revises: 0036_add_friend_health_columns
Create Date: 2026-03-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0037_add_workflow_pack_runtime_tables"
down_revision = "0036_add_friend_health_columns"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "workflow_gate_states" not in existing_tables:
        op.create_table(
            "workflow_gate_states",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workflow_key", sa.String(length=120), nullable=False),
            sa.Column("node_id", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="closed"),
            sa.Column("in_flight_run_id", sa.String(length=36)),
            sa.Column("last_control_signal", sa.String(length=32)),
            sa.Column("opened_at", sa.DateTime(timezone=True)),
            sa.Column("closed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        existing_tables.add("workflow_gate_states")
    if not _has_index(inspector, "workflow_gate_states", "ix_workflow_gate_states_workflow_node"):
        op.create_index(
            "ix_workflow_gate_states_workflow_node",
            "workflow_gate_states",
            ["workflow_key", "node_id"],
            unique=True,
        )

    if "workflow_gate_buffer_items" not in existing_tables:
        op.create_table(
            "workflow_gate_buffer_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workflow_key", sa.String(length=120), nullable=False),
            sa.Column("node_id", sa.String(length=120), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="buffered"),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("released_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("run_id", name="uq_workflow_gate_buffer_items_run_id"),
        )
        existing_tables.add("workflow_gate_buffer_items")
    if not _has_index(inspector, "workflow_gate_buffer_items", "ix_workflow_gate_buffer_items_gate_status"):
        op.create_index(
            "ix_workflow_gate_buffer_items_gate_status",
            "workflow_gate_buffer_items",
            ["workflow_key", "node_id", "status"],
        )
    if not _has_index(inspector, "workflow_gate_buffer_items", "ix_workflow_gate_buffer_items_run_id"):
        op.create_index("ix_workflow_gate_buffer_items_run_id", "workflow_gate_buffer_items", ["run_id"])

    if "workflow_build_tasks" not in existing_tables:
        op.create_table(
            "workflow_build_tasks",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("workflow_key", sa.String(length=120), nullable=False),
            sa.Column("task_type", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("result_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        existing_tables.add("workflow_build_tasks")
    if not _has_index(inspector, "workflow_build_tasks", "ix_workflow_build_tasks_workflow_status"):
        op.create_index(
            "ix_workflow_build_tasks_workflow_status",
            "workflow_build_tasks",
            ["workflow_key", "status"],
        )

    if "workflow_build_task_steps" not in existing_tables:
        op.create_table(
            "workflow_build_task_steps",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("task_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("detail", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not _has_index(inspector, "workflow_build_task_steps", "ix_workflow_build_task_steps_task_created_at"):
        op.create_index(
            "ix_workflow_build_task_steps_task_created_at",
            "workflow_build_task_steps",
            ["task_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_workflow_build_task_steps_task_created_at", table_name="workflow_build_task_steps")
    op.drop_table("workflow_build_task_steps")

    op.drop_index("ix_workflow_build_tasks_workflow_status", table_name="workflow_build_tasks")
    op.drop_table("workflow_build_tasks")

    op.drop_index("ix_workflow_gate_buffer_items_run_id", table_name="workflow_gate_buffer_items")
    op.drop_index("ix_workflow_gate_buffer_items_gate_status", table_name="workflow_gate_buffer_items")
    op.drop_table("workflow_gate_buffer_items")

    op.drop_index("ix_workflow_gate_states_workflow_node", table_name="workflow_gate_states")
    op.drop_table("workflow_gate_states")

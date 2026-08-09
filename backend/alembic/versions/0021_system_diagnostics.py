"""Add the persisted system diagnostic state.

Revision ID: 0021_system_diagnostics
Revises: 0020_agent_run_coordination
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0021_system_diagnostics"
down_revision = "0020_agent_run_coordination"
branch_labels = None
depends_on = None

TABLE_NAME = "system_diagnostic_state"
STATUS_INDEX = "ix_system_diagnostic_state_execution_status"


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _index_names() -> set[str]:
    if TABLE_NAME not in _table_names():
        return set()
    return {str(index["name"]) for index in inspect(op.get_bind()).get_indexes(TABLE_NAME) if index.get("name")}


def upgrade() -> None:
    if TABLE_NAME not in _table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("execution_status", sa.String(length=32), nullable=False, server_default="never"),
            sa.Column("overall_status", sa.String(length=32), nullable=False, server_default="unknown"),
            sa.Column("trigger_kind", sa.String(length=32), nullable=True),
            sa.Column("healthy_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("results_json", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if STATUS_INDEX not in _index_names():
        op.create_index(STATUS_INDEX, TABLE_NAME, ["execution_status"])


def downgrade() -> None:
    if TABLE_NAME not in _table_names():
        return
    if STATUS_INDEX in _index_names():
        op.drop_index(STATUS_INDEX, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)

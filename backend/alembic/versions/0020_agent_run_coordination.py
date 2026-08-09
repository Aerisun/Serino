"""Add durable agent run coordination metadata.

Revision ID: 0020_agent_run_coordination
Revises: 0019_asset_storage_layout
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0020_agent_run_coordination"
down_revision = "0019_asset_storage_layout"
branch_labels = None
depends_on = None

RUNS_TABLE = "agent_runs"
STEPS_TABLE = "agent_run_steps"

RUN_COLUMNS: tuple[sa.Column, ...] = (
    sa.Column("execution_mode", sa.String(length=24), nullable=False, server_default="live"),
    sa.Column("workflow_snapshot", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("workflow_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
    sa.Column("lease_owner", sa.String(length=255), nullable=True),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("retry_of_run_id", sa.String(length=36), nullable=True),
)

RUN_INDEXES: dict[str, tuple[list[str], bool]] = {
    "ix_agent_runs_claimable": (["status", "available_at", "created_at"], False),
    "ix_agent_runs_lease_expires_at": (["status", "lease_expires_at"], False),
    "uq_agent_runs_workflow_idempotency": (["workflow_key", "idempotency_key"], True),
}


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _table_names():
        return set()
    return {str(column["name"]) for column in inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> dict[str, dict[str, object]]:
    if table_name not in _table_names():
        return {}
    return {str(index["name"]): index for index in inspect(op.get_bind()).get_indexes(table_name) if index.get("name")}


def _has_unique_columns(table_name: str, column_names: list[str]) -> bool:
    expected = tuple(column_names)
    for index in _indexes(table_name).values():
        if bool(index.get("unique")) and tuple(index.get("column_names") or ()) == expected:
            return True
    for constraint in inspect(op.get_bind()).get_unique_constraints(table_name):
        if tuple(constraint.get("column_names") or ()) == expected:
            return True
    return False


def _resequence_legacy_run_steps() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, run_id, sequence_no
            FROM agent_run_steps
            ORDER BY run_id, sequence_no, created_at, id
            """
        )
    ).mappings()
    current_run_id: str | None = None
    next_sequence = 0
    for row in rows:
        run_id = str(row["run_id"])
        if run_id != current_run_id:
            current_run_id = run_id
            next_sequence = 0
        next_sequence += 1
        if int(row["sequence_no"]) == next_sequence:
            continue
        bind.execute(
            sa.text("UPDATE agent_run_steps SET sequence_no = :sequence_no WHERE id = :step_id"),
            {"sequence_no": next_sequence, "step_id": str(row["id"])},
        )


def upgrade() -> None:
    if RUNS_TABLE in _table_names():
        existing_columns = _columns(RUNS_TABLE)
        for column in RUN_COLUMNS:
            if column.name not in existing_columns:
                op.add_column(RUNS_TABLE, column)

        existing_indexes = _indexes(RUNS_TABLE)
        for name, (column_names, unique) in RUN_INDEXES.items():
            if name in existing_indexes:
                continue
            if unique and _has_unique_columns(RUNS_TABLE, column_names):
                continue
            op.create_index(name, RUNS_TABLE, column_names, unique=unique)

    if STEPS_TABLE in _table_names():
        step_indexes = _indexes(STEPS_TABLE)
        unique_columns = ["run_id", "sequence_no"]
        if "uq_agent_run_steps_run_sequence" not in step_indexes and not _has_unique_columns(
            STEPS_TABLE, unique_columns
        ):
            _resequence_legacy_run_steps()
            op.create_index(
                "uq_agent_run_steps_run_sequence",
                STEPS_TABLE,
                unique_columns,
                unique=True,
            )
        if "ix_agent_run_steps_run_id_sequence_no" in _indexes(STEPS_TABLE):
            op.drop_index("ix_agent_run_steps_run_id_sequence_no", table_name=STEPS_TABLE)


def downgrade() -> None:
    if STEPS_TABLE in _table_names():
        step_indexes = _indexes(STEPS_TABLE)
        if "uq_agent_run_steps_run_sequence" in step_indexes:
            op.drop_index("uq_agent_run_steps_run_sequence", table_name=STEPS_TABLE)
        if "ix_agent_run_steps_run_id_sequence_no" not in _indexes(STEPS_TABLE):
            op.create_index(
                "ix_agent_run_steps_run_id_sequence_no",
                STEPS_TABLE,
                ["run_id", "sequence_no"],
            )

    if RUNS_TABLE not in _table_names():
        return
    for name in RUN_INDEXES:
        if name in _indexes(RUNS_TABLE):
            op.drop_index(name, table_name=RUNS_TABLE)
    existing_columns = _columns(RUNS_TABLE)
    for column in reversed(RUN_COLUMNS):
        if column.name in existing_columns:
            op.drop_column(RUNS_TABLE, column.name)

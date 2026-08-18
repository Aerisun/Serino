"""Index Agent run steps used by the internal message activity projection.

Revision ID: 0024_agent_message_projection
Revises: 0023_agent_run_principal
Create Date: 2026-08-09
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0024_agent_message_projection"
down_revision = "0023_agent_run_principal"
branch_labels = None
depends_on = None

TABLE_NAME = "agent_run_steps"
INDEX_NAME = "ix_agent_run_steps_kind_created_at"


def _index_names() -> set[str]:
    inspector = inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return set()
    return {str(index["name"]) for index in inspector.get_indexes(TABLE_NAME) if index.get("name")}


def upgrade() -> None:
    if TABLE_NAME in inspect(op.get_bind()).get_table_names() and INDEX_NAME not in _index_names():
        op.create_index(INDEX_NAME, TABLE_NAME, ["step_kind", "created_at"])


def downgrade() -> None:
    if INDEX_NAME in _index_names():
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)

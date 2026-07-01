"""Add stable visit record ordering index.

Revision ID: 0007_visit_record_order_index
Revises: 0006_visit_record_user_agent_fields
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0007_visit_record_order_index"
down_revision = "0006_visit_record_user_agent_fields"
branch_labels = None
depends_on = None

TABLE = "visit_records"
INDEX = "ix_visit_records_visited_at_id"


def _indexes() -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    if INDEX not in _indexes():
        op.create_index(INDEX, TABLE, ["visited_at", "id"])


def downgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    if INDEX in _indexes():
        op.drop_index(INDEX, table_name=TABLE)

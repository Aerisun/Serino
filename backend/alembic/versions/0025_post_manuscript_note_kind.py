"""Add the manuscript or note kind for shared post content.

Revision ID: 0025_post_manuscript_note_kind
Revises: 0024_agent_message_projection
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0025_post_manuscript_note_kind"
down_revision = "0024_agent_message_projection"
branch_labels = None
depends_on = None

TABLE = "posts"
COLUMN = "kind"
INDEX = "ix_posts_kind"
DEFAULT_KIND = "manuscript"


def _column_names() -> set[str]:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return set()
    return {str(column["name"]) for column in inspect(bind).get_columns(TABLE)}


def _index_names() -> set[str]:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return set()
    return {str(index["name"]) for index in inspect(bind).get_indexes(TABLE) if index.get("name")}


def upgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    if COLUMN not in _column_names():
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.String(length=16), nullable=True, server_default=DEFAULT_KIND),
        )
        op.execute(f"UPDATE {TABLE} SET {COLUMN} = '{DEFAULT_KIND}' WHERE {COLUMN} IS NULL")
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.alter_column(
                COLUMN,
                existing_type=sa.String(length=16),
                nullable=False,
                server_default=DEFAULT_KIND,
            )
    if INDEX not in _index_names():
        op.create_index(INDEX, TABLE, [COLUMN])


def downgrade() -> None:
    if INDEX in _index_names():
        op.drop_index(INDEX, table_name=TABLE)
    if COLUMN in _column_names():
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_column(COLUMN)

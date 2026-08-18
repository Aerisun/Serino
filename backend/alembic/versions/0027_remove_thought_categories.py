"""Remove persisted categories from thoughts.

Revision ID: 0027_remove_thought_categories
Revises: 0026_manuscript_note_page_config
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_remove_thought_categories"
down_revision = "0026_manuscript_note_page_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "thoughts" in tables:
        thoughts = sa.table("thoughts", sa.column("category", sa.String(length=80)))
        bind.execute(thoughts.update().values(category=None))

    if "content_categories" in tables:
        categories = sa.table("content_categories", sa.column("content_type", sa.String(length=32)))
        bind.execute(categories.delete().where(categories.c.content_type == "thoughts"))


def downgrade() -> None:
    # The intentionally removed category values cannot be reconstructed.
    pass

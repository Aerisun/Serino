"""add site poem keyword preferences

Revision ID: 0013_add_site_poem_keywords
Revises: 0012_add_site_poem_source
Create Date: 2026-03-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_add_site_poem_keywords"
down_revision = "0012_add_site_poem_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.add_column(
            sa.Column(
                "poem_hitokoto_keywords",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.alter_column("poem_hitokoto_keywords", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("poem_hitokoto_keywords")

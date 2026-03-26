"""add site poem source settings

Revision ID: 0012_add_site_poem_source
Revises: 0011_expand_resume_configuration
Create Date: 2026-03-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_add_site_poem_source"
down_revision = "0011_expand_resume_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.add_column(sa.Column("poem_source", sa.String(length=40), nullable=False, server_default="custom"))
        batch_op.add_column(
            sa.Column(
                "poem_hitokoto_types",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.execute("UPDATE site_profile SET poem_hitokoto_types = '[\"d\", \"i\"]' WHERE poem_hitokoto_types = '[]'")

    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.alter_column("poem_source", server_default=None)
        batch_op.alter_column("poem_hitokoto_types", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("poem_hitokoto_types")
        batch_op.drop_column("poem_source")

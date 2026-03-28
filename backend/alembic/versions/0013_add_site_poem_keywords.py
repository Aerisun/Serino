"""add site poem keyword preferences

Revision ID: 0013_add_site_poem_keywords
Revises: 0012_add_site_poem_source
Create Date: 2026-03-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0013_add_site_poem_keywords"
down_revision = "0012_add_site_poem_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("site_profile")}

    if "poem_hitokoto_keywords" not in existing_columns:
        op.add_column(
            "site_profile",
            sa.Column(
                "poem_hitokoto_keywords",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("poem_hitokoto_keywords")

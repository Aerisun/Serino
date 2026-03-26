"""add asset note

Revision ID: 0015_add_asset_note
Revises: 0014_add_asset_resource_fields
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0015_add_asset_note"
down_revision = "0014_add_asset_resource_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "assets" not in inspector.get_table_names():
        return

    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("note", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("note")
"""Add tracking table for production data backfills.

Revision ID: 0052_add_data_migration_tracking
Revises: 0051_add_asset_remote_upload_queue
Create Date: 2026-04-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0052_add_data_migration_tracking"
down_revision = "0051_add_asset_remote_upload_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "_aerisun_data_migrations" not in inspector.get_table_names():
        op.create_table(
            "_aerisun_data_migrations",
            sa.Column("migration_key", sa.String(length=120), primary_key=True, nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "_aerisun_data_migrations" in inspector.get_table_names():
        op.drop_table("_aerisun_data_migrations")

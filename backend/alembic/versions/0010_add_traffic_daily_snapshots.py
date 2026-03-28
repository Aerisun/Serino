"""Add traffic daily snapshots table

Revision ID: 0010_add_traffic_daily_snapshots
Revises: 0009_add_image_max_bytes_to_community_config
Create Date: 2026-03-25 18:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0010_add_traffic_daily_snapshots"
down_revision: Union[str, None] = "0009_add_image_max_bytes_to_community_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("traffic_daily_snapshots"):
        return

    op.create_table(
        "traffic_daily_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("cumulative_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cumulative_reactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_date", "url", name="uq_traffic_daily_snapshots_date_url"),
    )
    op.create_index(
        "ix_traffic_daily_snapshots_snapshot_date",
        "traffic_daily_snapshots",
        ["snapshot_date"],
        unique=False,
    )
    op.create_index(
        "ix_traffic_daily_snapshots_url",
        "traffic_daily_snapshots",
        ["url"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("traffic_daily_snapshots"):
        return

    op.drop_index("ix_traffic_daily_snapshots_url", table_name="traffic_daily_snapshots")
    op.drop_index("ix_traffic_daily_snapshots_snapshot_date", table_name="traffic_daily_snapshots")
    op.drop_table("traffic_daily_snapshots")

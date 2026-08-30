"""Add background music configuration and ordered tracks.

Revision ID: 0028_background_music
Revises: 0027_remove_thought_categories
Create Date: 2026-08-30
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0028_background_music"
down_revision = "0027_remove_thought_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "background_music_config" not in tables:
        op.create_table(
            "background_music_config",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("playback_mode", sa.String(length=24), nullable=False, server_default="sequential"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    if "background_music_tracks" not in tables:
        op.create_table(
            "background_music_tracks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("asset_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("asset_id", name="uq_background_music_tracks_asset_id"),
        )
        op.create_index(
            "ix_background_music_tracks_order_index",
            "background_music_tracks",
            ["order_index"],
            unique=False,
        )
    config = sa.table(
        "background_music_config",
        sa.column("id", sa.String(length=36)),
        sa.column("enabled", sa.Boolean()),
        sa.column("playback_mode", sa.String(length=24)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    if bind.scalar(sa.select(sa.func.count()).select_from(config)) == 0:
        now = datetime.now(UTC)
        bind.execute(
            config.insert().values(
                id=str(uuid4()),
                enabled=False,
                playback_mode="sequential",
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_background_music_tracks_order_index", table_name="background_music_tracks")
    op.drop_table("background_music_tracks")
    op.drop_table("background_music_config")

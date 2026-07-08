"""Add public slug for assets.

Revision ID: 0013_asset_public_slug
Revises: 0012_backup_retention_days
Create Date: 2026-07-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0013_asset_public_slug"
down_revision = "0012_backup_retention_days"
branch_labels = None
depends_on = None

TABLE = "assets"
COLUMN = "public_slug"
INDEX = "ix_assets_public_slug"


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns() -> set[str]:
    if TABLE not in _table_names():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(TABLE)}


def _indexes() -> set[str]:
    if TABLE not in _table_names():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    if TABLE not in _table_names():
        return
    if COLUMN not in _columns():
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=160), nullable=True))
    if INDEX not in _indexes():
        op.create_index(INDEX, TABLE, [COLUMN], unique=True)


def downgrade() -> None:
    if TABLE not in _table_names():
        return
    if INDEX in _indexes():
        op.drop_index(INDEX, table_name=TABLE)
    if COLUMN in _columns():
        op.drop_column(TABLE, COLUMN)

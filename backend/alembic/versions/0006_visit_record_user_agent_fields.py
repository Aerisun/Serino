"""Add structured visitor analytics fields to visit_records.

Adds parsed User-Agent fields (browser/os/device + versions), client context
(screen, language), traffic-source fields (referrer domain, UTM params), the
query string, and a monthly-rotating visitor fingerprint.

Revision ID: 0006_visit_record_user_agent_fields
Revises: 0005_remove_content_status
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0006_visit_record_user_agent_fields"
down_revision = "0005_remove_content_status"
branch_labels = None
depends_on = None

TABLE = "visit_records"
NEW_COLUMNS = (
    ("query", sa.String(length=512)),
    ("visitor_id", sa.String(length=64)),
    ("browser", sa.String(length=64)),
    ("browser_version", sa.String(length=32)),
    ("os", sa.String(length=64)),
    ("os_version", sa.String(length=32)),
    ("device_type", sa.String(length=16)),
    ("screen", sa.String(length=16)),
    ("language", sa.String(length=35)),
    ("referer_domain", sa.String(length=255)),
    ("utm_source", sa.String(length=128)),
    ("utm_medium", sa.String(length=128)),
    ("utm_campaign", sa.String(length=128)),
    ("utm_term", sa.String(length=128)),
    ("utm_content", sa.String(length=128)),
)
NEW_INDEXES = (
    ("ix_visit_records_device_type", ["device_type"]),
    ("ix_visit_records_visitor_id_visited_at", ["visitor_id", "visited_at"]),
)


def _columns() -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(TABLE)}


def _indexes() -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    existing = _columns()
    for name, column_type in NEW_COLUMNS:
        if name not in existing:
            op.add_column(TABLE, sa.Column(name, column_type, nullable=True))
    existing_indexes = _indexes()
    for index_name, columns in NEW_INDEXES:
        if index_name not in existing_indexes:
            op.create_index(index_name, TABLE, columns)


def downgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    existing_indexes = _indexes()
    for index_name, _ in NEW_INDEXES:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=TABLE)
    existing = _columns()
    for name, _ in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column(TABLE, name)

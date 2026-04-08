"""Create the production baseline schema.

Revision ID: 0001_production_baseline
Revises:
Create Date: 2026-04-08
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aerisun.core.base import Base  # noqa: E402
from aerisun.core.data_migrations.state import DATA_MIGRATIONS_TABLE  # noqa: E402

import aerisun.domain.automation.models  # noqa: E402, F401
import aerisun.domain.content.models  # noqa: E402, F401
import aerisun.domain.engagement.models  # noqa: E402, F401
import aerisun.domain.iam.models  # noqa: E402, F401
import aerisun.domain.media.models  # noqa: E402, F401
import aerisun.domain.ops.models  # noqa: E402, F401
import aerisun.domain.site_auth.models  # noqa: E402, F401
import aerisun.domain.site_config.models  # noqa: E402, F401
import aerisun.domain.social.models  # noqa: E402, F401
import aerisun.domain.subscription.models  # noqa: E402, F401


revision = "0001_production_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    Base.metadata.create_all(bind=bind, checkfirst=True)

    if DATA_MIGRATIONS_TABLE not in inspector.get_table_names():
        op.create_table(
            DATA_MIGRATIONS_TABLE,
            sa.Column("migration_key", sa.String(length=120), primary_key=True, nullable=False),
            sa.Column("schema_revision", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("mode", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("checksum", sa.String(length=128), nullable=False),
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if DATA_MIGRATIONS_TABLE in inspector.get_table_names():
        op.drop_table(DATA_MIGRATIONS_TABLE)

    Base.metadata.drop_all(bind=bind, checkfirst=True)

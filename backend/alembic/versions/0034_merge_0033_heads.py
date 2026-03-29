"""merge 0033 heads

Revision ID: 0034_merge_0033_heads
Revises: 0033_add_backup_sync_tables, 0033_add_config_revisions
Create Date: 2026-03-29 10:15:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "0034_merge_0033_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0033_add_backup_sync_tables",
    "0033_add_config_revisions",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

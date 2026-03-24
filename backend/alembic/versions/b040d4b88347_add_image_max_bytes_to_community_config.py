"""add image_max_bytes to community_config

Revision ID: b040d4b88347
Revises: 0008_add_feature_flags
Create Date: 2026-03-23 11:36:51.899006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b040d4b88347'
down_revision: Union[str, None] = '0008_add_feature_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('community_config', sa.Column('image_max_bytes', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('community_config', 'image_max_bytes')

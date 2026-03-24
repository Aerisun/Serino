"""Add image_max_bytes to community_config

Revision ID: 0009_add_image_max_bytes_to_community_config
Revises: 0008_add_feature_flags
Create Date: 2026-03-23 11:36:51.899006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '0009_add_image_max_bytes_to_community_config'
down_revision: Union[str, None] = '0008_add_feature_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table('community_config'):
        return

    columns = {column['name'] for column in inspector.get_columns('community_config')}
    if 'image_max_bytes' not in columns:
        op.add_column('community_config', sa.Column('image_max_bytes', sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table('community_config'):
        return

    columns = {column['name'] for column in inspector.get_columns('community_config')}
    if 'image_max_bytes' in columns:
        with op.batch_alter_table('community_config') as batch_op:
            batch_op.drop_column('image_max_bytes')
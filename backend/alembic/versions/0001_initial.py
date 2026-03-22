from __future__ import annotations

from alembic import op

from aerisun.core.base import Base

# Import all domain models to register them on Base.metadata
import aerisun.domain.content.models  # noqa: F401
import aerisun.domain.engagement.models  # noqa: F401
import aerisun.domain.iam.models  # noqa: F401
import aerisun.domain.media.models  # noqa: F401
import aerisun.domain.ops.models  # noqa: F401
import aerisun.domain.site_config.models  # noqa: F401
import aerisun.domain.social.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

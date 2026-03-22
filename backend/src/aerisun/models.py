"""Barrel re-export of all ORM models for backward compatibility.

New code should import from domain-specific modules:
    from aerisun.domain.content.models import PostEntry
    from aerisun.domain.iam.models import AdminUser

This file ensures that ``from aerisun.models import X`` continues to work
for Alembic migrations, tests, and admin API routes.
"""

from __future__ import annotations

from aerisun.core.base import Base, ContentMixin, TimestampMixin, utcnow, uuid_str  # noqa: F401

from aerisun.domain.site_config.models import (  # noqa: F401
    CommunityConfig,
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
    SiteProfile,
    SocialLink,
)

from aerisun.domain.content.models import (  # noqa: F401
    DiaryEntry,
    ExcerptEntry,
    PostEntry,
    ThoughtEntry,
)

from aerisun.domain.engagement.models import (  # noqa: F401
    Comment,
    GuestbookEntry,
    Reaction,
)

from aerisun.domain.social.models import (  # noqa: F401
    Friend,
    FriendFeedItem,
    FriendFeedSource,
)

from aerisun.domain.iam.models import (  # noqa: F401
    AdminSession,
    AdminUser,
    ApiKey,
)

from aerisun.domain.media.models import Asset  # noqa: F401

from aerisun.domain.ops.models import (  # noqa: F401
    AuditLog,
    BackupSnapshot,
    ModerationRecord,
    RestorePoint,
    SyncRun,
)

"""Barrel re-export of all Pydantic schemas for backward compatibility.

New code should import from domain-specific modules:
    from aerisun.domain.content.schemas import ContentEntryRead
    from aerisun.domain.engagement.schemas import CommentRead

This file ensures that ``from aerisun.schemas import X`` continues to work
for API routes, tests, and other existing code.
"""

from __future__ import annotations

from aerisun.core.schemas import HealthRead, ModelBase  # noqa: F401

from aerisun.domain.site_config.schemas import (  # noqa: F401
    CommunityConfigRead,
    CommunitySurfaceRead,
    PageCollectionRead,
    PageCopyRead,
    PoemRead,
    ResumeExperienceRead,
    ResumeRead,
    ResumeSkillGroupRead,
    SiteConfigRead,
    SiteProfileRead,
    SocialLinkRead,
)

from aerisun.domain.content.schemas import (  # noqa: F401
    ContentCollectionRead,
    ContentEntryRead,
)

from aerisun.domain.engagement.schemas import (  # noqa: F401
    CommentCollectionRead,
    CommentCreate,
    CommentCreateResponse,
    CommentRead,
    GuestbookCollectionRead,
    GuestbookCreate,
    GuestbookCreateResponse,
    GuestbookEntryRead,
    ReactionCreate,
    ReactionRead,
)

from aerisun.domain.social.schemas import (  # noqa: F401
    FriendCollectionRead,
    FriendFeedCollectionRead,
    FriendFeedItemRead,
    FriendRead,
)

from aerisun.domain.activity.schemas import (  # noqa: F401
    ActivityHeatmapRead,
    ActivityHeatmapStatsRead,
    ActivityHeatmapWeekRead,
    CalendarEventRead,
    CalendarRead,
    RecentActivityItemRead,
    RecentActivityRead,
)

from __future__ import annotations

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase

# Re-export domain schemas for backward compatibility
from aerisun.domain.content.schemas import (  # noqa: F401
    CategoryInfo,
    ContentAdminRead,
    ContentCreate,
    ContentUpdate,
    ImportResult,
    SearchResponse,
    SearchResultItem,
    TagInfo,
)
from aerisun.domain.iam.schemas import (  # noqa: F401
    AdminProfileUpdate,
    AdminSessionRead,
    AdminUserRead,
    ApiKeyAdminRead,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyUpdate,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
)
from aerisun.domain.media.schemas import AssetAdminRead  # noqa: F401
from aerisun.domain.ops.schemas import (  # noqa: F401
    AuditLogRead,
    BackupSnapshotRead,
    CommentAdminRead,
    DashboardStats,
    EnhancedDashboardStats,
    GuestbookAdminRead,
    ModerateAction,
    MonthlyCount,
    RecentContentItem,
    SystemInfo,
)
from aerisun.domain.site_config.schemas import (  # noqa: F401
    CommunityConfigAdminRead,
    CommunityConfigUpdate,
    CommunitySurfaceUpdate,
    NavItemAdminRead,
    NavItemCreate,
    NavItemUpdate,
    NavReorderItem,
    PageCopyAdminRead,
    PageCopyCreate,
    PageCopyUpdate,
    PageDisplayOptionAdminRead,
    PageDisplayOptionCreate,
    PageDisplayOptionUpdate,
    PoemAdminRead,
    PoemCreate,
    PoemUpdate,
    ResumeBasicsAdminRead,
    ResumeBasicsCreate,
    ResumeBasicsUpdate,
    ResumeExperienceAdminRead,
    ResumeExperienceCreate,
    ResumeExperienceUpdate,
    ResumeSkillGroupAdminRead,
    ResumeSkillGroupCreate,
    ResumeSkillGroupUpdate,
    SiteProfileAdminRead,
    SiteProfileCreate,
    SiteProfileUpdate,
    SocialLinkAdminRead,
    SocialLinkCreate,
    SocialLinkUpdate,
)
from aerisun.domain.social.schemas import (  # noqa: F401
    FriendAdminRead,
    FriendCreate,
    FriendFeedSourceAdminRead,
    FriendFeedSourceCreate,
    FriendFeedSourceUpdate,
    FriendUpdate,
)

# ---------------------------------------------------------------------------
# Bulk operations (API-layer generic schemas -- stay here)
# ---------------------------------------------------------------------------


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(description="List of item IDs to delete")


class BulkStatusRequest(BaseModel):
    ids: list[str] = Field(description="List of item IDs to update")
    status: str = Field(description="New status value to set")


class BulkActionResponse(BaseModel):
    affected: int = Field(description="Number of items affected by the operation")


# ---------------------------------------------------------------------------
# Generic paginated response
# ---------------------------------------------------------------------------


class PaginatedResponse[ItemT](ModelBase):
    items: list[ItemT] = Field(description="Page of result items")
    total: int = Field(description="Total number of items matching the query")
    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")


# ---------------------------------------------------------------------------
# Feed crawl result schemas
# ---------------------------------------------------------------------------


class FeedCrawlResultRead(BaseModel):
    source_id: str = Field(description="ID of the crawled feed source")
    friend_name: str = Field(description="Name of the friend whose feed was crawled")
    status: str = Field(default="ok", description="Crawl status: ok or error")
    inserted: int = Field(default=0, description="Number of new items inserted")
    feed_url_updated: bool = Field(default=False, description="Whether the feed URL was updated due to redirect")
    error: str | None = Field(default=None, description="Error message if crawl failed")


class FeedCrawlAllResultRead(BaseModel):
    status: str = Field(default="completed", description="Overall crawl status")
    sources_crawled: int = Field(default=0, description="Total number of feed sources attempted")
    items_inserted: int = Field(default=0, description="Total new items inserted across all sources")
    errors: int = Field(default=0, description="Number of sources that failed")
    details: list[FeedCrawlResultRead] = Field(default_factory=list, description="Per-source crawl results")


# ---------------------------------------------------------------------------
# Comment image upload response
# ---------------------------------------------------------------------------


class CommentImageUploadData(BaseModel):
    url: str = Field(description="Public URL of the uploaded image")


class CommentImageUploadResponse(BaseModel):
    errno: int = Field(default=0, description="Error number, 0 for success")
    data: CommentImageUploadData = Field(description="Upload result data containing the image URL")

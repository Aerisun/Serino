from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(ModelBase):
    token: str
    expires_at: datetime


class AdminUserRead(ModelBase):
    id: str
    username: str
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Content (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)
# ---------------------------------------------------------------------------

class ContentCreate(BaseModel):
    slug: str
    title: str
    summary: str | None = None
    body: str
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    visibility: str = "public"
    published_at: datetime | None = None
    # Content-type specific fields
    category: str | None = None
    mood: str | None = None
    weather: str | None = None
    poem: str | None = None
    author_name: str | None = None
    source: str | None = None
    view_count: int = 0


class ContentUpdate(BaseModel):
    slug: str | None = None
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    visibility: str | None = None
    published_at: datetime | None = None
    category: str | None = None
    mood: str | None = None
    weather: str | None = None
    poem: str | None = None
    author_name: str | None = None
    source: str | None = None
    view_count: int | None = None


class ContentAdminRead(ModelBase):
    id: str
    slug: str
    title: str
    summary: str | None
    body: str
    tags: list[str]
    status: str
    visibility: str
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    category: str | None = None
    mood: str | None = None
    weather: str | None = None
    poem: str | None = None
    author_name: str | None = None
    source: str | None = None
    view_count: int = 0


# ---------------------------------------------------------------------------
# SiteProfile
# ---------------------------------------------------------------------------

class SiteProfileCreate(BaseModel):
    name: str
    title: str
    bio: str
    role: str
    footer_text: str
    author: str = ""
    og_image: str = "/images/hero_bg.jpeg"
    meta_description: str = ""
    copyright: str = "All rights reserved"
    hero_actions: str = "[]"
    hero_video_url: str | None = None


class SiteProfileUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    bio: str | None = None
    role: str | None = None
    footer_text: str | None = None
    author: str | None = None
    og_image: str | None = None
    meta_description: str | None = None
    copyright: str | None = None
    hero_actions: str | None = None
    hero_video_url: str | None = None


class SiteProfileAdminRead(ModelBase):
    id: str
    name: str
    title: str
    bio: str
    role: str
    footer_text: str
    author: str
    og_image: str
    meta_description: str
    copyright: str
    hero_actions: str
    hero_video_url: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# SocialLink
# ---------------------------------------------------------------------------

class SocialLinkCreate(BaseModel):
    site_profile_id: str
    name: str
    href: str
    icon_key: str
    placement: str = "hero"
    order_index: int = 0


class SocialLinkUpdate(BaseModel):
    name: str | None = None
    href: str | None = None
    icon_key: str | None = None
    placement: str | None = None
    order_index: int | None = None


class SocialLinkAdminRead(ModelBase):
    id: str
    site_profile_id: str
    name: str
    href: str
    icon_key: str
    placement: str
    order_index: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Poem
# ---------------------------------------------------------------------------

class PoemCreate(BaseModel):
    site_profile_id: str
    order_index: int = 0
    content: str


class PoemUpdate(BaseModel):
    order_index: int | None = None
    content: str | None = None


class PoemAdminRead(ModelBase):
    id: str
    site_profile_id: str
    order_index: int
    content: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# PageCopy
# ---------------------------------------------------------------------------

class PageCopyCreate(BaseModel):
    page_key: str
    label: str | None = None
    nav_label: str | None = None
    title: str
    subtitle: str
    description: str | None = None
    search_placeholder: str | None = None
    empty_message: str | None = None
    max_width: str | None = None
    page_size: int | None = None
    download_label: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class PageCopyUpdate(BaseModel):
    label: str | None = None
    nav_label: str | None = None
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    search_placeholder: str | None = None
    empty_message: str | None = None
    max_width: str | None = None
    page_size: int | None = None
    download_label: str | None = None
    extras: dict[str, Any] | None = None


class PageCopyAdminRead(ModelBase):
    id: str
    page_key: str
    label: str | None
    nav_label: str | None
    title: str
    subtitle: str
    description: str | None
    search_placeholder: str | None
    empty_message: str | None
    max_width: str | None
    page_size: int | None
    download_label: str | None
    extras: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# PageDisplayOption
# ---------------------------------------------------------------------------

class PageDisplayOptionCreate(BaseModel):
    page_key: str
    is_enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)


class PageDisplayOptionUpdate(BaseModel):
    is_enabled: bool | None = None
    settings: dict[str, Any] | None = None


class PageDisplayOptionAdminRead(ModelBase):
    id: str
    page_key: str
    is_enabled: bool
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# CommunityConfig
# ---------------------------------------------------------------------------

class CommunitySurfaceRead(BaseModel):
    key: str
    label: str
    path: str
    enabled: bool = True


class CommunitySurfaceUpdate(BaseModel):
    key: str | None = None
    label: str | None = None
    path: str | None = None
    enabled: bool | None = None


class CommunityConfigUpdate(BaseModel):
    provider: str | None = None
    server_url: str | None = None
    surfaces: list[CommunitySurfaceUpdate] | None = None
    meta: list[str] | None = None
    required_meta: list[str] | None = None
    emoji_presets: list[str] | None = None
    enable_enjoy_search: bool | None = None
    image_uploader: bool | None = None
    login_mode: str | None = None
    oauth_url: str | None = None
    oauth_providers: list[str] | None = None
    anonymous_enabled: bool | None = None
    moderation_mode: str | None = None
    default_sorting: str | None = None
    page_size: int | None = None
    avatar_presets: list[dict[str, Any]] | None = None
    guest_avatar_mode: str | None = None
    draft_enabled: bool | None = None
    avatar_strategy: str | None = None
    avatar_helper_copy: str | None = None
    migration_state: str | None = None


class CommunityConfigAdminRead(ModelBase):
    id: str
    provider: str
    server_url: str
    surfaces: list[CommunitySurfaceRead]
    meta: list[str]
    required_meta: list[str]
    emoji_presets: list[str]
    enable_enjoy_search: bool
    image_uploader: bool
    login_mode: str
    oauth_url: str | None
    oauth_providers: list[str]
    anonymous_enabled: bool
    moderation_mode: str
    default_sorting: str
    page_size: int
    avatar_presets: list[dict[str, Any]]
    guest_avatar_mode: str
    draft_enabled: bool
    avatar_strategy: str
    avatar_helper_copy: str
    migration_state: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class ResumeBasicsCreate(BaseModel):
    title: str
    subtitle: str
    summary: str
    download_label: str


class ResumeBasicsUpdate(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    summary: str | None = None
    download_label: str | None = None


class ResumeBasicsAdminRead(ModelBase):
    id: str
    title: str
    subtitle: str
    summary: str
    download_label: str
    created_at: datetime
    updated_at: datetime


class ResumeSkillGroupCreate(BaseModel):
    resume_basics_id: str
    category: str
    items: list[str] = Field(default_factory=list)
    order_index: int = 0


class ResumeSkillGroupUpdate(BaseModel):
    category: str | None = None
    items: list[str] | None = None
    order_index: int | None = None


class ResumeSkillGroupAdminRead(ModelBase):
    id: str
    resume_basics_id: str
    category: str
    items: list[str]
    order_index: int
    created_at: datetime
    updated_at: datetime


class ResumeExperienceCreate(BaseModel):
    resume_basics_id: str
    title: str
    company: str
    period: str
    summary: str
    order_index: int = 0


class ResumeExperienceUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    period: str | None = None
    summary: str | None = None
    order_index: int | None = None


class ResumeExperienceAdminRead(ModelBase):
    id: str
    resume_basics_id: str
    title: str
    company: str
    period: str
    summary: str
    order_index: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Friend
# ---------------------------------------------------------------------------

class FriendCreate(BaseModel):
    name: str
    url: str
    avatar_url: str | None = None
    description: str | None = None
    status: str = "active"
    order_index: int = 0


class FriendUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    avatar_url: str | None = None
    description: str | None = None
    status: str | None = None
    order_index: int | None = None


class FriendAdminRead(ModelBase):
    id: str
    name: str
    url: str
    avatar_url: str | None
    description: str | None
    status: str
    order_index: int
    created_at: datetime
    updated_at: datetime


class FriendFeedSourceCreate(BaseModel):
    friend_id: str
    feed_url: str
    is_enabled: bool = True


class FriendFeedSourceUpdate(BaseModel):
    feed_url: str | None = None
    is_enabled: bool | None = None


class FriendFeedSourceAdminRead(ModelBase):
    id: str
    friend_id: str
    feed_url: str
    last_fetched_at: datetime | None
    is_enabled: bool
    etag: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# NavItem
# ---------------------------------------------------------------------------

class NavItemCreate(BaseModel):
    site_profile_id: str
    parent_id: str | None = None
    label: str
    href: str | None = None
    icon_key: str | None = None
    page_key: str | None = None
    trigger: str = "none"
    order_index: int = 0
    is_enabled: bool = True


class NavItemUpdate(BaseModel):
    parent_id: str | None = None
    label: str | None = None
    href: str | None = None
    icon_key: str | None = None
    page_key: str | None = None
    trigger: str | None = None
    order_index: int | None = None
    is_enabled: bool | None = None


class NavItemAdminRead(ModelBase):
    id: str
    site_profile_id: str
    parent_id: str | None
    label: str
    href: str | None
    icon_key: str | None
    page_key: str | None
    trigger: str
    order_index: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class NavReorderItem(BaseModel):
    id: str
    parent_id: str | None = None
    order_index: int


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------

class CommentAdminRead(ModelBase):
    id: str
    content_type: str
    content_slug: str
    parent_id: str | None
    author_name: str
    author_email: str | None
    body: str
    status: str
    created_at: datetime
    updated_at: datetime


class GuestbookAdminRead(ModelBase):
    id: str
    name: str
    email: str | None
    website: str | None
    body: str
    status: str
    created_at: datetime
    updated_at: datetime


class ModerateAction(BaseModel):
    action: str  # "approve", "reject", "delete"
    reason: str | None = None


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

class AssetAdminRead(ModelBase):
    id: str
    file_name: str
    storage_path: str
    mime_type: str | None
    byte_size: int | None
    sha256: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    key_name: str
    scopes: list[str] = Field(default_factory=list)


class ApiKeyUpdate(BaseModel):
    key_name: str | None = None
    scopes: list[str] | None = None


class ApiKeyAdminRead(ModelBase):
    id: str
    key_name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApiKeyCreateResponse(ModelBase):
    item: ApiKeyAdminRead
    raw_key: str


class AuditLogRead(ModelBase):
    id: str
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class BackupSnapshotRead(ModelBase):
    id: str
    snapshot_type: str
    status: str
    db_path: str
    replica_url: str | None
    backup_path: str | None
    checksum: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DashboardStats(ModelBase):
    posts: int
    diary_entries: int
    thoughts: int
    excerpts: int
    comments: int
    guestbook_entries: int
    friends: int
    assets: int


# ---------------------------------------------------------------------------
# Generic paginated response
# ---------------------------------------------------------------------------

class PaginatedResponse(ModelBase):
    items: list[Any]
    total: int
    page: int
    page_size: int

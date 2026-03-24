from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(description="Admin username")
    password: str = Field(description="Admin password")


class LoginResponse(ModelBase):
    token: str = Field(description="JWT authentication token")
    expires_at: datetime = Field(description="Token expiration timestamp")


class AdminUserRead(ModelBase):
    id: str = Field(description="Unique user identifier")
    username: str = Field(description="Admin username")
    is_active: bool = Field(description="Whether the account is active")
    created_at: datetime = Field(description="Account creation timestamp")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(description="Current password for verification")
    new_password: str = Field(description="New password to set")


class AdminProfileUpdate(BaseModel):
    username: str | None = Field(default=None, description="New username to set")


class AdminSessionRead(ModelBase):
    id: str = Field(description="Session identifier")
    created_at: datetime = Field(description="Session creation timestamp")
    expires_at: datetime = Field(description="Session expiration timestamp")
    is_current: bool = Field(default=False, description="Whether this is the current active session")


# ---------------------------------------------------------------------------
# Content (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)
# ---------------------------------------------------------------------------


class ContentCreate(BaseModel):
    slug: str = Field(description="URL-friendly unique identifier")
    title: str = Field(description="Display title")
    summary: str | None = Field(default=None, description="Brief summary or excerpt")
    body: str = Field(description="Full content body in Markdown")
    tags: list[str] = Field(default_factory=list, description="List of tag names")
    status: str = Field(default="draft", description="Publication status: draft, published, or archived")
    visibility: str = Field(default="public", description="Visibility level: public or private")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")
    category: str | None = Field(default=None, description="Content category name")
    mood: str | None = Field(default=None, description="Author mood (diary-specific)")
    weather: str | None = Field(default=None, description="Weather description (diary-specific)")
    poem: str | None = Field(default=None, description="Associated poem text")
    author_name: str | None = Field(default=None, description="Original author name (for excerpts)")
    source: str | None = Field(default=None, description="Source URL or reference (for excerpts)")
    view_count: int = Field(default=0, description="Manual view count override")
    is_pinned: bool = Field(default=False, description="Whether pinned to top")
    pin_order: int = Field(default=0, description="Sort order among pinned items")


class ContentUpdate(BaseModel):
    slug: str | None = Field(default=None, description="URL-friendly unique identifier")
    title: str | None = Field(default=None, description="Display title")
    summary: str | None = Field(default=None, description="Brief summary or excerpt")
    body: str | None = Field(default=None, description="Full content body in Markdown")
    tags: list[str] | None = Field(default=None, description="List of tag names")
    status: str | None = Field(default=None, description="Publication status")
    visibility: str | None = Field(default=None, description="Visibility level")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")
    category: str | None = Field(default=None, description="Content category name")
    mood: str | None = Field(default=None, description="Author mood (diary-specific)")
    weather: str | None = Field(default=None, description="Weather description (diary-specific)")
    poem: str | None = Field(default=None, description="Associated poem text")
    author_name: str | None = Field(default=None, description="Original author name")
    source: str | None = Field(default=None, description="Source URL or reference")
    view_count: int | None = Field(default=None, description="Manual view count override")
    is_pinned: bool | None = Field(default=None, description="Whether pinned to top")
    pin_order: int | None = Field(default=None, description="Sort order among pinned items")


class ContentAdminRead(ModelBase):
    id: str = Field(description="Unique content identifier")
    slug: str = Field(description="URL-friendly unique identifier")
    title: str = Field(description="Display title")
    summary: str | None = Field(description="Brief summary or excerpt")
    body: str = Field(description="Full content body in Markdown")
    tags: list[str] = Field(description="List of tag names")
    status: str = Field(description="Publication status")
    visibility: str = Field(description="Visibility level")
    published_at: datetime | None = Field(description="Publication timestamp")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    category: str | None = Field(default=None, description="Content category")
    mood: str | None = Field(default=None, description="Author mood (diary-specific)")
    weather: str | None = Field(default=None, description="Weather description (diary-specific)")
    poem: str | None = Field(default=None, description="Associated poem text")
    author_name: str | None = Field(default=None, description="Original author name")
    source: str | None = Field(default=None, description="Source URL or reference")
    view_count: int = Field(default=0, description="Total page views")
    is_pinned: bool = Field(default=False, description="Whether pinned to top")
    pin_order: int = Field(default=0, description="Sort order among pinned items")


# ---------------------------------------------------------------------------
# SiteProfile
# ---------------------------------------------------------------------------


class SiteProfileCreate(BaseModel):
    name: str = Field(description="Site owner display name")
    title: str = Field(description="Site title shown in header and SEO")
    bio: str = Field(description="Short biography")
    role: str = Field(description="Professional role or tagline")
    footer_text: str = Field(description="Text shown in site footer")
    author: str = Field(default="", description="Default author name for meta tags")
    og_image: str = Field(default="/images/hero_bg.jpeg", description="Default Open Graph image path")
    meta_description: str = Field(default="", description="Default meta description for SEO")
    copyright: str = Field(default="All rights reserved", description="Copyright notice text")
    hero_actions: str = Field(default="[]", description="JSON string of hero section action buttons")
    hero_video_url: str | None = Field(default=None, description="URL for hero background video")


class SiteProfileUpdate(BaseModel):
    name: str | None = Field(default=None, description="Site owner display name")
    title: str | None = Field(default=None, description="Site title")
    bio: str | None = Field(default=None, description="Short biography")
    role: str | None = Field(default=None, description="Professional role or tagline")
    footer_text: str | None = Field(default=None, description="Footer text")
    author: str | None = Field(default=None, description="Default author name")
    og_image: str | None = Field(default=None, description="Open Graph image path")
    meta_description: str | None = Field(default=None, description="Meta description for SEO")
    copyright: str | None = Field(default=None, description="Copyright notice")
    hero_actions: str | None = Field(default=None, description="Hero action buttons JSON")
    hero_video_url: str | None = Field(default=None, description="Hero background video URL")
    feature_flags: dict[str, object] | None = Field(default=None, description="Feature toggle flags")


class SiteProfileAdminRead(ModelBase):
    id: str = Field(description="Unique profile identifier")
    name: str = Field(description="Site owner display name")
    title: str = Field(description="Site title")
    bio: str = Field(description="Short biography")
    role: str = Field(description="Professional role or tagline")
    footer_text: str = Field(description="Footer text")
    author: str = Field(description="Default author name")
    og_image: str = Field(description="Open Graph image path")
    meta_description: str = Field(description="Meta description")
    copyright: str = Field(description="Copyright notice")
    hero_actions: str = Field(description="Hero action buttons JSON")
    hero_video_url: str | None = Field(description="Hero background video URL")
    feature_flags: dict[str, object] = Field(description="Feature toggle flags")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# SocialLink
# ---------------------------------------------------------------------------


class SocialLinkCreate(BaseModel):
    site_profile_id: str | None = Field(default=None, description="Associated site profile ID")
    name: str = Field(description="Social platform display name")
    href: str = Field(description="Social profile URL")
    icon_key: str = Field(description="Icon identifier for rendering")
    placement: str = Field(default="hero", description="Display location: hero or footer")
    order_index: int = Field(default=0, description="Sort order (lower first)")


class SocialLinkUpdate(BaseModel):
    name: str | None = Field(default=None, description="Social platform display name")
    href: str | None = Field(default=None, description="Social profile URL")
    icon_key: str | None = Field(default=None, description="Icon identifier")
    placement: str | None = Field(default=None, description="Display location")
    order_index: int | None = Field(default=None, description="Sort order")


class SocialLinkAdminRead(ModelBase):
    id: str = Field(description="Unique social link identifier")
    site_profile_id: str = Field(description="Associated site profile ID")
    name: str = Field(description="Social platform name")
    href: str = Field(description="Social profile URL")
    icon_key: str = Field(description="Icon identifier")
    placement: str = Field(description="Display location")
    order_index: int = Field(description="Sort order")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Poem
# ---------------------------------------------------------------------------


class PoemCreate(BaseModel):
    site_profile_id: str | None = Field(default=None, description="Associated site profile ID")
    order_index: int = Field(default=0, description="Display order (lower first)")
    content: str = Field(description="Poem text content")


class PoemUpdate(BaseModel):
    order_index: int | None = Field(default=None, description="Display order")
    content: str | None = Field(default=None, description="Poem text content")


class PoemAdminRead(ModelBase):
    id: str = Field(description="Unique poem identifier")
    site_profile_id: str = Field(description="Associated site profile ID")
    order_index: int = Field(description="Display order")
    content: str = Field(description="Poem text content")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# PageCopy
# ---------------------------------------------------------------------------


class PageCopyCreate(BaseModel):
    page_key: str = Field(description="Unique page identifier key")
    label: str | None = Field(default=None, description="Sidebar or menu label")
    nav_label: str | None = Field(default=None, description="Navigation menu label override")
    title: str = Field(description="Page title heading")
    subtitle: str = Field(description="Page subtitle text")
    description: str | None = Field(default=None, description="Page meta description")
    search_placeholder: str | None = Field(default=None, description="Search input placeholder text")
    empty_message: str | None = Field(default=None, description="Message shown when no content exists")
    max_width: str | None = Field(default=None, description="Maximum page width CSS value")
    page_size: int | None = Field(default=None, description="Default items per page")
    download_label: str | None = Field(default=None, description="Download button label text")
    extras: dict[str, Any] = Field(default_factory=dict, description="Additional page-specific configuration")


class PageCopyUpdate(BaseModel):
    label: str | None = Field(default=None, description="Sidebar label")
    nav_label: str | None = Field(default=None, description="Navigation label override")
    title: str | None = Field(default=None, description="Page title heading")
    subtitle: str | None = Field(default=None, description="Page subtitle text")
    description: str | None = Field(default=None, description="Page meta description")
    search_placeholder: str | None = Field(default=None, description="Search placeholder")
    empty_message: str | None = Field(default=None, description="Empty state message")
    max_width: str | None = Field(default=None, description="Maximum page width")
    page_size: int | None = Field(default=None, description="Default items per page")
    download_label: str | None = Field(default=None, description="Download button label")
    extras: dict[str, Any] | None = Field(default=None, description="Additional configuration")


class PageCopyAdminRead(ModelBase):
    id: str = Field(description="Unique page copy identifier")
    page_key: str = Field(description="Page identifier key")
    label: str | None = Field(description="Sidebar label")
    nav_label: str | None = Field(description="Navigation label override")
    title: str = Field(description="Page title heading")
    subtitle: str = Field(description="Page subtitle text")
    description: str | None = Field(description="Page meta description")
    search_placeholder: str | None = Field(description="Search placeholder")
    empty_message: str | None = Field(description="Empty state message")
    max_width: str | None = Field(description="Maximum page width")
    page_size: int | None = Field(description="Default items per page")
    download_label: str | None = Field(description="Download button label")
    extras: dict[str, Any] = Field(description="Additional configuration")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# PageDisplayOption
# ---------------------------------------------------------------------------


class PageDisplayOptionCreate(BaseModel):
    page_key: str = Field(description="Page identifier key")
    is_enabled: bool = Field(default=True, description="Whether the page is enabled")
    settings: dict[str, Any] = Field(default_factory=dict, description="Page display settings")


class PageDisplayOptionUpdate(BaseModel):
    is_enabled: bool | None = Field(default=None, description="Whether the page is enabled")
    settings: dict[str, Any] | None = Field(default=None, description="Page display settings")


class PageDisplayOptionAdminRead(ModelBase):
    id: str = Field(description="Unique display option identifier")
    page_key: str = Field(description="Page identifier key")
    is_enabled: bool = Field(description="Whether the page is enabled")
    settings: dict[str, Any] = Field(description="Page display settings")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# CommunityConfig
# ---------------------------------------------------------------------------


class CommunitySurfaceRead(BaseModel):
    key: str = Field(description="Surface identifier key")
    label: str = Field(description="Display label")
    path: str = Field(description="URL path pattern")
    enabled: bool = Field(default=True, description="Whether comments are enabled")


class CommunitySurfaceUpdate(BaseModel):
    key: str | None = Field(default=None, description="Surface identifier key")
    label: str | None = Field(default=None, description="Display label")
    path: str | None = Field(default=None, description="URL path pattern")
    enabled: bool | None = Field(default=None, description="Whether comments are enabled")


class CommunityConfigUpdate(BaseModel):
    provider: str | None = Field(default=None, description="Comment system provider name")
    server_url: str | None = Field(default=None, description="Comment server URL")
    surfaces: list[CommunitySurfaceUpdate] | None = Field(default=None, description="Comment-enabled surfaces")
    meta: list[str] | None = Field(default=None, description="Commenter metadata fields")
    required_meta: list[str] | None = Field(default=None, description="Required metadata fields")
    emoji_presets: list[str] | None = Field(default=None, description="Emoji preset CDN URLs")
    enable_enjoy_search: bool | None = Field(default=None, description="Enable emoji search")
    image_uploader: bool | None = Field(default=None, description="Allow image uploads in comments")
    login_mode: str | None = Field(default=None, description="Authentication mode")
    oauth_url: str | None = Field(default=None, description="OAuth endpoint URL")
    oauth_providers: list[str] | None = Field(default=None, description="Enabled OAuth providers")
    anonymous_enabled: bool | None = Field(default=None, description="Allow anonymous commenting")
    moderation_mode: str | None = Field(default=None, description="Comment moderation mode")
    default_sorting: str | None = Field(default=None, description="Default comment sort order")
    page_size: int | None = Field(default=None, description="Comments per page")
    image_max_bytes: int | None = Field(default=None, description="Max upload image size in bytes")
    avatar_presets: list[dict[str, Any]] | None = Field(default=None, description="Predefined avatar options")
    guest_avatar_mode: str | None = Field(default=None, description="Guest avatar display mode")
    draft_enabled: bool | None = Field(default=None, description="Allow saving comment drafts")
    avatar_strategy: str | None = Field(default=None, description="Avatar resolution strategy")
    avatar_helper_copy: str | None = Field(default=None, description="Avatar selection helper text")
    migration_state: str | None = Field(default=None, description="Waline migration state")


class CommunityConfigAdminRead(ModelBase):
    id: str = Field(description="Unique community config identifier")
    provider: str = Field(description="Comment system provider")
    server_url: str = Field(description="Comment server URL")
    surfaces: list[CommunitySurfaceRead] = Field(description="Comment-enabled surfaces")
    meta: list[str] = Field(description="Commenter metadata fields")
    required_meta: list[str] = Field(description="Required metadata fields")
    emoji_presets: list[str] = Field(description="Emoji preset CDN URLs")
    enable_enjoy_search: bool = Field(description="Emoji search enabled")
    image_uploader: bool = Field(description="Image uploads allowed")
    login_mode: str = Field(description="Authentication mode")
    oauth_url: str | None = Field(description="OAuth endpoint URL")
    oauth_providers: list[str] = Field(description="Enabled OAuth providers")
    anonymous_enabled: bool = Field(description="Anonymous commenting allowed")
    moderation_mode: str = Field(description="Comment moderation mode")
    default_sorting: str = Field(description="Default sort order")
    page_size: int = Field(description="Comments per page")
    image_max_bytes: int | None = Field(default=524288, description="Max upload image size in bytes")
    avatar_presets: list[dict[str, Any]] = Field(description="Predefined avatar options")
    guest_avatar_mode: str = Field(description="Guest avatar mode")
    draft_enabled: bool = Field(description="Draft saving enabled")
    avatar_strategy: str = Field(description="Avatar resolution strategy")
    avatar_helper_copy: str = Field(description="Avatar helper text")
    migration_state: str = Field(description="Waline migration state")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------


class ResumeBasicsCreate(BaseModel):
    title: str = Field(description="Resume page title")
    subtitle: str = Field(description="Resume subtitle or tagline")
    summary: str = Field(description="Professional summary paragraph")
    download_label: str = Field(description="PDF download button label")


class ResumeBasicsUpdate(BaseModel):
    title: str | None = Field(default=None, description="Resume page title")
    subtitle: str | None = Field(default=None, description="Resume subtitle")
    summary: str | None = Field(default=None, description="Professional summary")
    download_label: str | None = Field(default=None, description="Download button label")


class ResumeBasicsAdminRead(ModelBase):
    id: str = Field(description="Unique resume basics identifier")
    title: str = Field(description="Resume page title")
    subtitle: str = Field(description="Resume subtitle")
    summary: str = Field(description="Professional summary")
    download_label: str = Field(description="Download button label")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ResumeSkillGroupCreate(BaseModel):
    resume_basics_id: str | None = Field(default=None, description="Associated resume basics ID")
    category: str = Field(description="Skill category name")
    items: list[str] = Field(default_factory=list, description="List of skill names")
    order_index: int = Field(default=0, description="Display order (lower first)")


class ResumeSkillGroupUpdate(BaseModel):
    category: str | None = Field(default=None, description="Skill category name")
    items: list[str] | None = Field(default=None, description="List of skill names")
    order_index: int | None = Field(default=None, description="Display order")


class ResumeSkillGroupAdminRead(ModelBase):
    id: str = Field(description="Unique skill group identifier")
    resume_basics_id: str = Field(description="Associated resume basics ID")
    category: str = Field(description="Skill category name")
    items: list[str] = Field(description="List of skill names")
    order_index: int = Field(description="Display order")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ResumeExperienceCreate(BaseModel):
    resume_basics_id: str | None = Field(default=None, description="Associated resume basics ID")
    title: str = Field(description="Job title or role")
    company: str = Field(description="Company or organization name")
    period: str = Field(description="Employment period (e.g. 2020-2023)")
    summary: str = Field(description="Role description and achievements")
    order_index: int = Field(default=0, description="Display order (lower first)")


class ResumeExperienceUpdate(BaseModel):
    title: str | None = Field(default=None, description="Job title")
    company: str | None = Field(default=None, description="Company name")
    period: str | None = Field(default=None, description="Employment period")
    summary: str | None = Field(default=None, description="Role description")
    order_index: int | None = Field(default=None, description="Display order")


class ResumeExperienceAdminRead(ModelBase):
    id: str = Field(description="Unique experience identifier")
    resume_basics_id: str = Field(description="Associated resume basics ID")
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    period: str = Field(description="Employment period")
    summary: str = Field(description="Role description")
    order_index: int = Field(description="Display order")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Friend
# ---------------------------------------------------------------------------


class FriendCreate(BaseModel):
    name: str = Field(description="Friend site display name")
    url: str = Field(description="Friend site URL")
    avatar_url: str | None = Field(default=None, description="Avatar image URL")
    description: str | None = Field(default=None, description="Short description of the friend site")
    status: str = Field(default="active", description="Link status: active or inactive")
    order_index: int = Field(default=0, description="Display order (lower first)")


class FriendUpdate(BaseModel):
    name: str | None = Field(default=None, description="Friend site display name")
    url: str | None = Field(default=None, description="Friend site URL")
    avatar_url: str | None = Field(default=None, description="Avatar image URL")
    description: str | None = Field(default=None, description="Short description")
    status: str | None = Field(default=None, description="Link status")
    order_index: int | None = Field(default=None, description="Display order")


class FriendAdminRead(ModelBase):
    id: str = Field(description="Unique friend identifier")
    name: str = Field(description="Friend site display name")
    url: str = Field(description="Friend site URL")
    avatar_url: str | None = Field(description="Avatar image URL")
    description: str | None = Field(description="Short description")
    status: str = Field(description="Link status")
    order_index: int = Field(description="Display order")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class FriendFeedSourceCreate(BaseModel):
    friend_id: str = Field(description="Associated friend ID")
    feed_url: str = Field(description="RSS/Atom feed URL")
    is_enabled: bool = Field(default=True, description="Whether to actively crawl this feed")


class FriendFeedSourceUpdate(BaseModel):
    feed_url: str | None = Field(default=None, description="RSS/Atom feed URL")
    is_enabled: bool | None = Field(default=None, description="Whether to actively crawl")


class FriendFeedSourceAdminRead(ModelBase):
    id: str = Field(description="Unique feed source identifier")
    friend_id: str = Field(description="Associated friend ID")
    feed_url: str = Field(description="RSS/Atom feed URL")
    last_fetched_at: datetime | None = Field(description="Last successful fetch timestamp")
    is_enabled: bool = Field(description="Whether actively crawled")
    etag: str | None = Field(default=None, description="HTTP ETag for conditional requests")
    last_error: str | None = Field(default=None, description="Last crawl error message")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# NavItem
# ---------------------------------------------------------------------------


class NavItemCreate(BaseModel):
    site_profile_id: str | None = Field(default=None, description="Associated site profile ID")
    parent_id: str | None = Field(default=None, description="Parent nav item ID for nested items")
    label: str = Field(description="Navigation menu label")
    href: str | None = Field(default=None, description="Navigation link URL")
    icon_key: str | None = Field(default=None, description="Icon identifier for rendering")
    page_key: str | None = Field(default=None, description="Associated page key")
    trigger: str = Field(default="none", description="Interaction trigger type: none, hover, or click")
    order_index: int = Field(default=0, description="Display order (lower first)")
    is_enabled: bool = Field(default=True, description="Whether the nav item is visible")


class NavItemUpdate(BaseModel):
    parent_id: str | None = Field(default=None, description="Parent nav item ID")
    label: str | None = Field(default=None, description="Navigation label")
    href: str | None = Field(default=None, description="Link URL")
    icon_key: str | None = Field(default=None, description="Icon identifier")
    page_key: str | None = Field(default=None, description="Associated page key")
    trigger: str | None = Field(default=None, description="Interaction trigger type")
    order_index: int | None = Field(default=None, description="Display order")
    is_enabled: bool | None = Field(default=None, description="Whether visible")


class NavItemAdminRead(ModelBase):
    id: str = Field(description="Unique nav item identifier")
    site_profile_id: str = Field(description="Associated site profile ID")
    parent_id: str | None = Field(description="Parent nav item ID")
    label: str = Field(description="Navigation label")
    href: str | None = Field(description="Link URL")
    icon_key: str | None = Field(description="Icon identifier")
    page_key: str | None = Field(description="Associated page key")
    trigger: str = Field(description="Interaction trigger type")
    order_index: int = Field(description="Display order")
    is_enabled: bool = Field(description="Whether visible")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class NavReorderItem(BaseModel):
    id: str = Field(description="Nav item ID to reorder")
    parent_id: str | None = Field(default=None, description="New parent nav item ID")
    order_index: int = Field(description="New display order position")


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------


class CommentAdminRead(ModelBase):
    id: str = Field(description="Unique comment identifier")
    content_type: str = Field(description="Content type: posts, diary, thoughts, or excerpts")
    content_slug: str = Field(description="Slug of the commented content")
    parent_id: str | None = Field(description="Parent comment ID for replies")
    author_name: str = Field(description="Comment author display name")
    author_email: str | None = Field(description="Comment author email address")
    body: str = Field(description="Comment body text")
    status: str = Field(description="Moderation status: approved, waiting, or spam")
    created_at: datetime = Field(description="Comment creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class GuestbookAdminRead(ModelBase):
    id: str = Field(description="Unique guestbook entry identifier")
    name: str = Field(description="Guest display name")
    email: str | None = Field(description="Guest email address")
    website: str | None = Field(description="Guest personal website URL")
    body: str = Field(description="Guestbook message body")
    status: str = Field(description="Moderation status")
    created_at: datetime = Field(description="Entry creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ModerateAction(BaseModel):
    action: str = Field(description="Moderation action: approve, reject, or delete")
    reason: str | None = Field(default=None, description="Optional reason for the moderation action")


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


class AssetAdminRead(ModelBase):
    id: str = Field(description="Unique asset identifier")
    file_name: str = Field(description="Original uploaded file name")
    storage_path: str = Field(description="Server file system storage path")
    mime_type: str | None = Field(description="MIME type of the file")
    byte_size: int | None = Field(description="File size in bytes")
    sha256: str | None = Field(description="SHA-256 hash of the file content")
    created_at: datetime = Field(description="Upload timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    key_name: str = Field(description="Descriptive name for the API key")
    scopes: list[str] = Field(default_factory=list, description="List of permission scopes")


class ApiKeyUpdate(BaseModel):
    key_name: str | None = Field(default=None, description="Descriptive name for the API key")
    scopes: list[str] | None = Field(default=None, description="List of permission scopes")


class ApiKeyAdminRead(ModelBase):
    id: str = Field(description="Unique API key identifier")
    key_name: str = Field(description="Descriptive name")
    key_prefix: str = Field(description="First 8 characters for identification")
    scopes: list[str] = Field(description="Permission scopes")
    last_used_at: datetime | None = Field(description="Last API call timestamp")
    created_at: datetime = Field(description="Key creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ApiKeyCreateResponse(ModelBase):
    item: ApiKeyAdminRead = Field(description="Created API key details")
    raw_key: str = Field(description="Full API key value (shown only once)")


class AuditLogRead(ModelBase):
    id: str = Field(description="Unique audit log identifier")
    actor_type: str = Field(description="Type of actor: admin or api_key")
    actor_id: str | None = Field(description="Identifier of the actor")
    action: str = Field(description="Action performed")
    target_type: str | None = Field(description="Type of the affected resource")
    target_id: str | None = Field(description="Identifier of the affected resource")
    payload: dict[str, Any] = Field(description="Additional action details and metadata")
    created_at: datetime = Field(description="Action timestamp")


class BackupSnapshotRead(ModelBase):
    id: str = Field(description="Unique backup identifier")
    snapshot_type: str = Field(description="Backup type: manual or scheduled")
    status: str = Field(description="Backup status: queued, completed, or failed")
    db_path: str = Field(description="Database file path")
    replica_url: str | None = Field(description="Litestream replica URL")
    backup_path: str | None = Field(description="Backup archive file path")
    checksum: str | None = Field(description="Backup file checksum")
    completed_at: datetime | None = Field(description="Backup completion timestamp")
    created_at: datetime = Field(description="Backup creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MonthlyCount(BaseModel):
    month: str = Field(description="Month identifier in YYYY-MM format")
    posts: int = Field(default=0, description="Number of posts created")
    diary: int = Field(default=0, description="Number of diary entries created")
    thoughts: int = Field(default=0, description="Number of thoughts created")
    excerpts: int = Field(default=0, description="Number of excerpts created")


class RecentContentItem(BaseModel):
    id: str = Field(description="Content item identifier")
    title: str = Field(description="Content title")
    content_type: str = Field(description="Type: post, diary, thought, or excerpt")
    status: str = Field(description="Publication status")
    updated_at: datetime = Field(description="Last update timestamp")


class DashboardStats(ModelBase):
    posts: int = Field(description="Total number of posts")
    diary_entries: int = Field(description="Total number of diary entries")
    thoughts: int = Field(description="Total number of thoughts")
    excerpts: int = Field(description="Total number of excerpts")
    comments: int = Field(description="Total number of comments")
    guestbook_entries: int = Field(description="Total number of guestbook entries")
    friends: int = Field(description="Total number of friend links")
    assets: int = Field(description="Total number of uploaded assets")


class EnhancedDashboardStats(ModelBase):
    posts: int = Field(description="Total number of posts")
    diary_entries: int = Field(description="Total number of diary entries")
    thoughts: int = Field(description="Total number of thoughts")
    excerpts: int = Field(description="Total number of excerpts")
    comments: int = Field(description="Total number of comments")
    guestbook_entries: int = Field(description="Total number of guestbook entries")
    friends: int = Field(description="Total number of friend links")
    assets: int = Field(description="Total number of uploaded assets")
    posts_by_status: dict[str, int] = Field(default_factory=dict, description="Post counts grouped by status")
    content_by_month: list[MonthlyCount] = Field(default_factory=list, description="Content creation counts per month")
    recent_content: list[RecentContentItem] = Field(default_factory=list, description="Most recently updated content items")


class SystemInfo(BaseModel):
    version: str = Field(default="1.0.0", description="Application version")
    python_version: str = Field(description="Python runtime version")
    db_size_bytes: int = Field(description="SQLite database file size in bytes")
    media_dir_size_bytes: int = Field(description="Total media directory size in bytes")
    uptime_seconds: float = Field(description="Server uptime in seconds")
    environment: str = Field(description="Deployment environment name")


# ---------------------------------------------------------------------------
# Bulk operations
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


class PaginatedResponse(ModelBase, Generic[T]):
    items: list[T] = Field(description="Page of result items")
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

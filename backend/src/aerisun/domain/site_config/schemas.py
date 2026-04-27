from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from aerisun.core.schemas import ModelBase

COMMENT_MODERATION_MODE_ALL_PENDING = "all_pending"
COMMENT_MODERATION_MODE_NO_REVIEW = "no_review"


def _normalize_media_reference_value(
    value: str | None,
    *,
    empty_as_none: bool = False,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None if empty_as_none else ""
    return text


def normalize_comment_moderation_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"no_review", "none", "off", "disabled"}:
        return COMMENT_MODERATION_MODE_NO_REVIEW
    return COMMENT_MODERATION_MODE_ALL_PENDING


class SocialLinkRead(ModelBase):
    name: str = Field(description="Social platform display name")
    href: str = Field(description="Social profile URL")
    icon_key: str = Field(description="Icon identifier")
    placement: str = Field(description="Display location: hero or footer")
    order_index: int = Field(description="Sort order")


class PoemRead(ModelBase):
    content: str = Field(description="Poem text content")
    order_index: int = Field(description="Display order")


class SiteProfileRead(ModelBase):
    name: str = Field(description="Site owner name")
    title: str = Field(description="Site title")
    bio: str = Field(description="Short biography")
    role: str = Field(description="Professional role")
    og_image: str = Field(description="Open Graph/Twitter sharing image path")
    site_icon_url: str = Field(description="Browser tab icon path")
    hero_image_url: str = Field(description="Hero image path")
    hero_poster_url: str = Field(description="Hero video poster and fallback background image path")
    filing_info: str = Field(description="Regulatory filing or ICP notice")
    hero_actions: list[dict[str, object]] = Field(description="Hero section action buttons")
    hero_video_url: str | None = Field(default=None, description="Hero background video URL")
    poem_source: Literal["custom", "hitokoto"] = Field(default="hitokoto", description="Poem source mode")
    poem_hitokoto_types: list[str] = Field(default_factory=list, description="Hitokoto category codes")
    poem_hitokoto_keywords: list[str] = Field(default_factory=list, description="Hitokoto preferred keywords")
    feature_flags: dict[str, object] = Field(default_factory=dict, description="Feature toggle flags")


class NavChildRead(ModelBase):
    label: str = Field(description="Child navigation label")
    href: str = Field(description="Child navigation URL")


class NavItemRead(ModelBase):
    label: str = Field(description="Navigation item label")
    trigger: str = Field(description="Interaction trigger type")
    href: str | None = Field(default=None, description="Navigation URL")
    children: list[NavChildRead] = Field(default_factory=list, description="Nested child navigation items")


class SiteConfigRead(ModelBase):
    site: SiteProfileRead = Field(description="Site profile configuration")
    social_links: list[SocialLinkRead] = Field(description="Social media links")
    poems: list[PoemRead] = Field(description="Featured poems")
    navigation: list[NavItemRead] = Field(default_factory=list, description="Navigation menu items")


class SitePoemPreviewRead(ModelBase):
    mode: Literal["custom", "hitokoto"] = Field(description="Resolved poem source mode")
    content: str = Field(description="Poem content shown on the homepage")
    attribution: str | None = Field(default=None, description="Optional source attribution")


class LinkPreviewRead(ModelBase):
    url: str = Field(description="Original normalized URL")
    resolved_url: str = Field(description="Resolved URL after redirects or canonical resolution")
    hostname: str = Field(description="Resolved hostname")
    title: str | None = Field(default=None, description="Resolved page title")
    description: str | None = Field(default=None, description="Resolved page description")
    site_name: str | None = Field(default=None, description="Resolved site name")
    image_url: str | None = Field(default=None, description="Preview image URL")
    image_width: int | None = Field(default=None, description="Preview image width if declared")
    image_height: int | None = Field(default=None, description="Preview image height if declared")
    icon_url: str | None = Field(default=None, description="Site icon URL")
    available: bool = Field(default=True, description="Whether preview metadata was successfully fetched")
    error: str | None = Field(default=None, description="Optional fetch error detail")


class PageCopyRead(ModelBase):
    page_key: str = Field(description="Page identifier key")
    title: str = Field(description="Page title")
    subtitle: str = Field(description="Page subtitle")
    search_placeholder: str | None = Field(description="Search placeholder text")
    empty_message: str | None = Field(description="Empty state message")
    max_width: str | None = Field(description="Max page width CSS value")
    page_size: int | None = Field(description="Items per page")
    extras: dict[str, object] = Field(description="Additional configuration")


class PageCollectionRead(ModelBase):
    items: list[PageCopyRead] = Field(description="List of page configurations")


class CommunitySurfaceRead(ModelBase):
    key: str = Field(description="Surface identifier")
    label: str = Field(description="Display label")
    path: str = Field(description="URL path pattern")
    enabled: bool = Field(description="Whether comments are enabled")


class CommunityConfigRead(ModelBase):
    provider: str = Field(description="Comment provider name")
    server_url: str = Field(description="Comment server URL")
    surfaces: list[CommunitySurfaceRead] = Field(description="Comment-enabled surfaces")
    meta: list[str] = Field(description="Commenter metadata fields")
    required_meta: list[str] = Field(description="Required metadata fields")
    emoji_presets: list[str] = Field(description="Emoji preset CDN URLs")
    image_uploader: bool = Field(description="Image uploads allowed")
    anonymous_enabled: bool = Field(description="Whether email login is allowed for commenting")
    moderation_mode: str = Field(description="Moderation mode")
    default_sorting: str = Field(description="Default sort order")
    page_size: int = Field(description="Initial comments loaded per batch")
    image_max_bytes: int | None = Field(default=524288, description="Max image upload size in bytes")
    avatar_helper_copy: str = Field(description="Avatar helper text")
    migration_state: str = Field(description="Migration progress state")

    @field_validator("moderation_mode", mode="before")
    @classmethod
    def validate_moderation_mode(cls, value: str | None) -> str:
        return normalize_comment_moderation_mode(value)


class ResumeRead(ModelBase):
    title: str = Field(description="Resume page title")
    summary: str = Field(description="Professional summary")
    location: str = Field(default="", description="Current base location")
    email: str = Field(default="", description="Primary contact email")
    profile_image_url: str = Field(default="", description="Profile image URL")


class SiteBootstrapRead(ModelBase):
    revision: str = Field(description="Stable revision hash for the current public site bootstrap payload")
    generated_at: datetime = Field(description="上海时间戳，表示当前站点引导数据生成时间")
    site: SiteConfigRead = Field(description="Site profile and navigation bundle")
    pages: PageCollectionRead = Field(description="Page copy bundle")
    resume: ResumeRead = Field(description="Resume basics bundle")


# ---------------------------------------------------------------------------
# Admin: SiteProfile
# ---------------------------------------------------------------------------


class SiteProfileCreate(BaseModel):
    name: str = Field(description="Site owner display name")
    title: str = Field(description="Site title shown in header and SEO")
    bio: str = Field(description="Short biography")
    role: str = Field(description="Professional role or tagline")
    og_image: str = Field(default="", description="Default Open Graph/Twitter sharing image path")
    site_icon_url: str = Field(default="", description="Browser tab icon path")
    hero_image_url: str = Field(default="", description="Hero image path")
    hero_poster_url: str = Field(default="", description="Hero video poster and fallback background image path")
    filing_info: str = Field(default="", description="Regulatory filing or ICP notice")
    hero_actions: str = Field(default="[]", description="JSON string of hero section action buttons")
    hero_video_url: str | None = Field(default=None, description="URL for hero background video")
    poem_source: Literal["custom", "hitokoto"] = Field(default="hitokoto", description="Poem source mode")
    poem_hitokoto_types: list[str] = Field(default_factory=list, description="Hitokoto category codes")
    poem_hitokoto_keywords: list[str] = Field(default_factory=list, description="Hitokoto preferred keywords")

    @field_validator("og_image", "site_icon_url", "hero_image_url", "hero_poster_url", "hero_video_url", mode="before")
    @classmethod
    def validate_registered_media_urls(cls, value: str | None, info) -> str | None:
        normalized = _normalize_media_reference_value(
            value,
            empty_as_none=info.field_name == "hero_video_url",
        )
        if info.field_name == "hero_video_url":
            return normalized
        return normalized or ""


class SiteProfileUpdate(BaseModel):
    name: str | None = Field(default=None, description="Site owner display name")
    title: str | None = Field(default=None, description="Site title")
    bio: str | None = Field(default=None, description="Short biography")
    role: str | None = Field(default=None, description="Professional role or tagline")
    og_image: str | None = Field(default=None, description="Open Graph/Twitter sharing image path")
    site_icon_url: str | None = Field(default=None, description="Browser tab icon path")
    hero_image_url: str | None = Field(default=None, description="Hero image path")
    hero_poster_url: str | None = Field(
        default=None, description="Hero video poster and fallback background image path"
    )
    filing_info: str | None = Field(default=None, description="Regulatory filing or ICP notice")
    hero_actions: str | None = Field(default=None, description="Hero action buttons JSON")
    hero_video_url: str | None = Field(default=None, description="Hero background video URL")
    poem_source: Literal["custom", "hitokoto"] | None = Field(default=None, description="Poem source mode")
    poem_hitokoto_types: list[str] | None = Field(default=None, description="Hitokoto category codes")
    poem_hitokoto_keywords: list[str] | None = Field(default=None, description="Hitokoto preferred keywords")
    feature_flags: dict[str, object] | None = Field(default=None, description="Feature toggle flags")

    @field_validator("og_image", "site_icon_url", "hero_image_url", "hero_poster_url", "hero_video_url", mode="before")
    @classmethod
    def validate_registered_media_urls(cls, value: str | None, info) -> str | None:
        return _normalize_media_reference_value(
            value,
            empty_as_none=True,
        )


class SiteProfileAdminRead(ModelBase):
    id: str = Field(description="Unique profile identifier")
    name: str = Field(description="Site owner display name")
    title: str = Field(description="Site title")
    bio: str = Field(description="Short biography")
    role: str = Field(description="Professional role or tagline")
    og_image: str = Field(description="Open Graph/Twitter sharing image path")
    site_icon_url: str = Field(description="Browser tab icon path")
    hero_image_url: str = Field(description="Hero image path")
    hero_poster_url: str = Field(description="Hero video poster and fallback background image path")
    filing_info: str = Field(description="Regulatory filing or ICP notice")
    hero_actions: str = Field(description="Hero action buttons JSON")
    hero_video_url: str | None = Field(description="Hero background video URL")
    poem_source: Literal["custom", "hitokoto"] = Field(description="Poem source mode")
    poem_hitokoto_types: list[str] = Field(description="Hitokoto category codes")
    poem_hitokoto_keywords: list[str] = Field(description="Hitokoto preferred keywords")
    feature_flags: dict[str, object] = Field(description="Feature toggle flags")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Admin: SocialLink
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
# Admin: Poem
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
# Admin: PageCopy
# ---------------------------------------------------------------------------


class PageCopyCreate(BaseModel):
    page_key: str = Field(description="Unique page identifier key")
    title: str = Field(description="Page title heading")
    subtitle: str = Field(description="Page subtitle text")
    search_placeholder: str | None = Field(default=None, description="Search input placeholder text")
    empty_message: str | None = Field(default=None, description="Message shown when no content exists")
    max_width: str | None = Field(default=None, description="Maximum page width CSS value")
    page_size: int | None = Field(default=None, ge=1, le=30, description="Default items per page")
    extras: dict[str, Any] = Field(default_factory=dict, description="Additional page-specific configuration")


class PageCopyUpdate(BaseModel):
    title: str | None = Field(default=None, description="Page title heading")
    subtitle: str | None = Field(default=None, description="Page subtitle text")
    search_placeholder: str | None = Field(default=None, description="Search placeholder")
    empty_message: str | None = Field(default=None, description="Empty state message")
    max_width: str | None = Field(default=None, description="Maximum page width")
    page_size: int | None = Field(default=None, ge=1, le=30, description="Default items per page")
    extras: dict[str, Any] | None = Field(default=None, description="Additional configuration")


class PageCopyAdminRead(ModelBase):
    id: str = Field(description="Unique page copy identifier")
    page_key: str = Field(description="Page identifier key")
    title: str = Field(description="Page title heading")
    subtitle: str = Field(description="Page subtitle text")
    search_placeholder: str | None = Field(description="Search placeholder")
    empty_message: str | None = Field(description="Empty state message")
    max_width: str | None = Field(description="Maximum page width")
    page_size: int | None = Field(description="Default items per page")
    extras: dict[str, Any] = Field(description="Additional configuration")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Admin: CommunityConfig
# ---------------------------------------------------------------------------


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
    image_uploader: bool | None = Field(default=None, description="Allow image uploads in comments")
    anonymous_enabled: bool | None = Field(default=None, description="Allow email login for commenting")
    moderation_mode: str | None = Field(default=None, description="Comment moderation mode")
    default_sorting: str | None = Field(default=None, description="Default comment sort order")
    page_size: int | None = Field(default=None, description="Initial comments loaded per batch")
    image_max_bytes: int | None = Field(default=None, description="Max upload image size in bytes")
    comment_image_rate_limit_count: int | None = Field(
        default=None,
        ge=1,
        le=60,
        description="Allowed comment image uploads per rate limit window",
    )
    comment_image_rate_limit_window_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description="Comment image upload rate limit window in minutes",
    )
    avatar_helper_copy: str | None = Field(default=None, description="Avatar selection helper text")
    migration_state: str | None = Field(default=None, description="Waline migration state")

    @field_validator("moderation_mode", mode="before")
    @classmethod
    def validate_moderation_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_comment_moderation_mode(value)


class CommunityConfigAdminRead(ModelBase):
    id: str = Field(description="Unique community config identifier")
    provider: str = Field(description="Comment system provider")
    server_url: str = Field(description="Comment server URL")
    surfaces: list[CommunitySurfaceRead] = Field(description="Comment-enabled surfaces")
    meta: list[str] = Field(description="Commenter metadata fields")
    required_meta: list[str] = Field(description="Required metadata fields")
    emoji_presets: list[str] = Field(description="Emoji preset CDN URLs")
    image_uploader: bool = Field(description="Image uploads allowed")
    anonymous_enabled: bool = Field(description="Whether email login is allowed for commenting")
    moderation_mode: str = Field(description="Comment moderation mode")
    default_sorting: str = Field(description="Default sort order")
    page_size: int = Field(description="Initial comments loaded per batch")
    image_max_bytes: int | None = Field(default=524288, description="Max upload image size in bytes")
    comment_image_rate_limit_count: int = Field(description="Allowed comment image uploads per rate limit window")
    comment_image_rate_limit_window_minutes: int = Field(
        description="Comment image upload rate limit window in minutes"
    )
    avatar_helper_copy: str = Field(description="Avatar helper text")
    migration_state: str = Field(description="Waline migration state")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    @field_validator("moderation_mode", mode="before")
    @classmethod
    def validate_moderation_mode(cls, value: str | None) -> str:
        return normalize_comment_moderation_mode(value)


# ---------------------------------------------------------------------------
# Admin: Resume
# ---------------------------------------------------------------------------


class ResumeBasicsCreate(BaseModel):
    title: str = Field(description="Resume page title")
    summary: str = Field(description="Markdown resume body")
    location: str = Field(default="", description="Current base location")
    email: str = Field(default="", description="Primary contact email")
    profile_image_url: str = Field(default="", description="Profile image URL")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def validate_profile_image_url(cls, value: str | None) -> str:
        return _normalize_media_reference_value(value) or ""


class ResumeBasicsUpdate(BaseModel):
    title: str | None = Field(default=None, description="Resume page title")
    summary: str | None = Field(default=None, description="Markdown resume body")
    location: str | None = Field(default=None, description="Current base location")
    email: str | None = Field(default=None, description="Primary contact email")
    profile_image_url: str | None = Field(default=None, description="Profile image URL")

    @field_validator("profile_image_url", mode="before")
    @classmethod
    def validate_profile_image_url(cls, value: str | None) -> str | None:
        return _normalize_media_reference_value(value, empty_as_none=True)


class ResumeBasicsAdminRead(ModelBase):
    id: str = Field(description="Unique resume basics identifier")
    title: str = Field(description="Resume page title")
    summary: str = Field(description="Markdown resume body")
    location: str = Field(description="Current base location")
    email: str = Field(description="Primary contact email")
    profile_image_url: str = Field(description="Profile image URL")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Admin: NavItem
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

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


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
    footer_text: str = Field(description="Footer text")
    author: str = Field(description="Default author name")
    og_image: str = Field(description="Open Graph image path")
    site_icon_url: str = Field(description="Browser tab icon path")
    hero_image_url: str = Field(description="Hero image path")
    hero_poster_url: str = Field(description="Hero video poster image path")
    meta_description: str = Field(description="Meta description for SEO")
    copyright: str = Field(description="Copyright notice")
    hero_actions: list[dict[str, object]] = Field(description="Hero section action buttons")
    hero_video_url: str | None = Field(default=None, description="Hero background video URL")
    poem_source: Literal["custom", "hitokoto"] = Field(default="custom", description="Poem source mode")
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


class PageCopyRead(ModelBase):
    page_key: str = Field(description="Page identifier key")
    label: str | None = Field(description="Sidebar label")
    nav_label: str | None = Field(description="Navigation label override")
    title: str = Field(description="Page title")
    subtitle: str = Field(description="Page subtitle")
    description: str | None = Field(description="Page description")
    search_placeholder: str | None = Field(description="Search placeholder text")
    empty_message: str | None = Field(description="Empty state message")
    max_width: str | None = Field(description="Max page width CSS value")
    page_size: int | None = Field(description="Items per page")
    download_label: str | None = Field(description="Download button label")
    enabled: bool = Field(description="Whether the page is enabled")
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
    enable_enjoy_search: bool = Field(description="Emoji search enabled")
    image_uploader: bool = Field(description="Image uploads allowed")
    login_mode: str = Field(description="Authentication mode, fixed to login-required")
    oauth_url: str | None = Field(description="OAuth endpoint URL")
    oauth_providers: list[str] = Field(description="OAuth provider names")
    anonymous_enabled: bool = Field(description="Whether email login is allowed for commenting")
    moderation_mode: str = Field(description="Moderation mode")
    default_sorting: str = Field(description="Default sort order")
    page_size: int = Field(description="Initial comments loaded per batch")
    image_max_bytes: int | None = Field(default=524288, description="Max image upload size in bytes")
    avatar_presets: list[dict[str, Any]] = Field(description="Predefined avatar options")
    guest_avatar_mode: str = Field(description="Guest avatar mode")
    draft_enabled: bool = Field(description="Draft saving enabled")
    avatar_strategy: str = Field(description="Avatar resolution strategy")
    avatar_helper_copy: str = Field(description="Avatar helper text")
    migration_state: str = Field(description="Migration progress state")


class ResumeSkillGroupRead(ModelBase):
    category: str = Field(description="Skill category name")
    items: list[str] = Field(description="Skill names in this category")
    order_index: int = Field(description="Display order")


class ResumeExperienceRead(ModelBase):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    period: str = Field(description="Employment period")
    location: str = Field(default="", description="Experience location")
    employment_type: str = Field(default="", description="Employment type")
    summary: str = Field(description="Role description")
    achievements: list[str] = Field(default_factory=list, description="Achievement bullet points")
    tech_stack: list[str] = Field(default_factory=list, description="Technologies used")
    order_index: int = Field(description="Display order")


class ResumeRead(ModelBase):
    title: str = Field(description="Resume page title")
    summary: str = Field(description="Professional summary")
    location: str = Field(default="", description="Current base location")
    email: str = Field(default="", description="Primary contact email")
    profile_image_url: str = Field(default="", description="Profile image URL")


# ---------------------------------------------------------------------------
# Admin: SiteProfile
# ---------------------------------------------------------------------------


class SiteProfileCreate(BaseModel):
    name: str = Field(description="Site owner display name")
    title: str = Field(description="Site title shown in header and SEO")
    bio: str = Field(description="Short biography")
    role: str = Field(description="Professional role or tagline")
    footer_text: str = Field(description="Text shown in site footer")
    author: str = Field(default="", description="Default author name for meta tags")
    og_image: str = Field(default="", description="Default Open Graph image path")
    site_icon_url: str = Field(default="", description="Browser tab icon path")
    hero_image_url: str = Field(default="", description="Hero image path")
    hero_poster_url: str = Field(default="", description="Hero video poster image path")
    meta_description: str = Field(default="", description="Default meta description for SEO")
    copyright: str = Field(default="All rights reserved", description="Copyright notice text")
    hero_actions: str = Field(default="[]", description="JSON string of hero section action buttons")
    hero_video_url: str | None = Field(default=None, description="URL for hero background video")
    poem_source: Literal["custom", "hitokoto"] = Field(default="custom", description="Poem source mode")
    poem_hitokoto_types: list[str] = Field(default_factory=list, description="Hitokoto category codes")
    poem_hitokoto_keywords: list[str] = Field(default_factory=list, description="Hitokoto preferred keywords")


class SiteProfileUpdate(BaseModel):
    name: str | None = Field(default=None, description="Site owner display name")
    title: str | None = Field(default=None, description="Site title")
    bio: str | None = Field(default=None, description="Short biography")
    role: str | None = Field(default=None, description="Professional role or tagline")
    footer_text: str | None = Field(default=None, description="Footer text")
    author: str | None = Field(default=None, description="Default author name")
    og_image: str | None = Field(default=None, description="Open Graph image path")
    site_icon_url: str | None = Field(default=None, description="Browser tab icon path")
    hero_image_url: str | None = Field(default=None, description="Hero image path")
    hero_poster_url: str | None = Field(default=None, description="Hero video poster image path")
    meta_description: str | None = Field(default=None, description="Meta description for SEO")
    copyright: str | None = Field(default=None, description="Copyright notice")
    hero_actions: str | None = Field(default=None, description="Hero action buttons JSON")
    hero_video_url: str | None = Field(default=None, description="Hero background video URL")
    poem_source: Literal["custom", "hitokoto"] | None = Field(default=None, description="Poem source mode")
    poem_hitokoto_types: list[str] | None = Field(default=None, description="Hitokoto category codes")
    poem_hitokoto_keywords: list[str] | None = Field(default=None, description="Hitokoto preferred keywords")
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
    site_icon_url: str = Field(description="Browser tab icon path")
    hero_image_url: str = Field(description="Hero image path")
    hero_poster_url: str = Field(description="Hero video poster image path")
    meta_description: str = Field(description="Meta description")
    copyright: str = Field(description="Copyright notice")
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
# Admin: PageDisplayOption
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
    enable_enjoy_search: bool | None = Field(default=None, description="Enable emoji search")
    image_uploader: bool | None = Field(default=None, description="Allow image uploads in comments")
    login_mode: str | None = Field(default=None, description="Authentication mode, fixed to login-required")
    oauth_url: str | None = Field(default=None, description="OAuth endpoint URL")
    oauth_providers: list[str] | None = Field(default=None, description="Enabled OAuth providers")
    anonymous_enabled: bool | None = Field(default=None, description="Allow email login for commenting")
    moderation_mode: str | None = Field(default=None, description="Comment moderation mode")
    default_sorting: str | None = Field(default=None, description="Default comment sort order")
    page_size: int | None = Field(default=None, description="Initial comments loaded per batch")
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
    login_mode: str = Field(description="Authentication mode, fixed to login-required")
    oauth_url: str | None = Field(description="OAuth endpoint URL")
    oauth_providers: list[str] = Field(description="Enabled OAuth providers")
    anonymous_enabled: bool = Field(description="Whether email login is allowed for commenting")
    moderation_mode: str = Field(description="Comment moderation mode")
    default_sorting: str = Field(description="Default sort order")
    page_size: int = Field(description="Initial comments loaded per batch")
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
# Admin: Resume
# ---------------------------------------------------------------------------


class ResumeBasicsCreate(BaseModel):
    title: str = Field(description="Resume page title")
    summary: str = Field(description="Markdown resume body")
    location: str = Field(default="", description="Current base location")
    email: str = Field(default="", description="Primary contact email")
    profile_image_url: str = Field(default="", description="Profile image URL")


class ResumeBasicsUpdate(BaseModel):
    title: str | None = Field(default=None, description="Resume page title")
    summary: str | None = Field(default=None, description="Markdown resume body")
    location: str | None = Field(default=None, description="Current base location")
    email: str | None = Field(default=None, description="Primary contact email")
    profile_image_url: str | None = Field(default=None, description="Profile image URL")


class ResumeBasicsAdminRead(ModelBase):
    id: str = Field(description="Unique resume basics identifier")
    title: str = Field(description="Resume page title")
    summary: str = Field(description="Markdown resume body")
    location: str = Field(description="Current base location")
    email: str = Field(description="Primary contact email")
    profile_image_url: str = Field(description="Profile image URL")
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
    location: str = Field(default="", description="Experience location")
    employment_type: str = Field(default="", description="Employment type")
    summary: str = Field(description="Role description and achievements")
    achievements: list[str] = Field(default_factory=list, description="Achievement bullet points")
    tech_stack: list[str] = Field(default_factory=list, description="Technologies used")
    order_index: int = Field(default=0, description="Display order (lower first)")


class ResumeExperienceUpdate(BaseModel):
    title: str | None = Field(default=None, description="Job title")
    company: str | None = Field(default=None, description="Company name")
    period: str | None = Field(default=None, description="Employment period")
    location: str | None = Field(default=None, description="Experience location")
    employment_type: str | None = Field(default=None, description="Employment type")
    summary: str | None = Field(default=None, description="Role description")
    achievements: list[str] | None = Field(default=None, description="Achievement bullet points")
    tech_stack: list[str] | None = Field(default=None, description="Technologies used")
    order_index: int | None = Field(default=None, description="Display order")


class ResumeExperienceAdminRead(ModelBase):
    id: str = Field(description="Unique experience identifier")
    resume_basics_id: str = Field(description="Associated resume basics ID")
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    period: str = Field(description="Employment period")
    location: str = Field(description="Experience location")
    employment_type: str = Field(description="Employment type")
    summary: str = Field(description="Role description")
    achievements: list[str] = Field(description="Achievement bullet points")
    tech_stack: list[str] = Field(description="Technologies used")
    order_index: int = Field(description="Display order")
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

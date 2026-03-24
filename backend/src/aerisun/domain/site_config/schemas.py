from __future__ import annotations

from typing import Any

from pydantic import Field

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
    meta_description: str = Field(description="Meta description for SEO")
    copyright: str = Field(description="Copyright notice")
    hero_actions: list[dict[str, object]] = Field(description="Hero section action buttons")
    hero_video_url: str | None = Field(default=None, description="Hero background video URL")
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
    login_mode: str = Field(description="Authentication mode")
    oauth_url: str | None = Field(description="OAuth endpoint URL")
    oauth_providers: list[str] = Field(description="OAuth provider names")
    anonymous_enabled: bool = Field(description="Anonymous commenting allowed")
    moderation_mode: str = Field(description="Moderation mode")
    default_sorting: str = Field(description="Default sort order")
    page_size: int = Field(description="Comments per page")
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
    summary: str = Field(description="Role description")
    order_index: int = Field(description="Display order")


class ResumeRead(ModelBase):
    title: str = Field(description="Resume page title")
    subtitle: str = Field(description="Resume subtitle")
    summary: str = Field(description="Professional summary")
    download_label: str = Field(description="PDF download label")
    skill_groups: list[ResumeSkillGroupRead] = Field(description="Skill categories and items")
    experiences: list[ResumeExperienceRead] = Field(description="Work experience entries")

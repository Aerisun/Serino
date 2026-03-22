from __future__ import annotations

from typing import Any

from pydantic import Field

from aerisun.core.schemas import ModelBase


class SocialLinkRead(ModelBase):
    name: str
    href: str
    icon_key: str
    placement: str
    order_index: int


class PoemRead(ModelBase):
    content: str
    order_index: int


class SiteProfileRead(ModelBase):
    name: str
    title: str
    bio: str
    role: str
    footer_text: str
    author: str
    og_image: str
    meta_description: str
    copyright: str
    hero_actions: list[dict[str, object]]
    hero_video_url: str | None = None
    feature_flags: dict[str, object] = Field(default_factory=dict)


class NavChildRead(ModelBase):
    label: str
    href: str


class NavItemRead(ModelBase):
    label: str
    trigger: str
    href: str | None = None
    children: list[NavChildRead] = Field(default_factory=list)


class SiteConfigRead(ModelBase):
    site: SiteProfileRead
    social_links: list[SocialLinkRead]
    poems: list[PoemRead]
    navigation: list[NavItemRead] = Field(default_factory=list)


class PageCopyRead(ModelBase):
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
    enabled: bool
    extras: dict[str, object]


class PageCollectionRead(ModelBase):
    items: list[PageCopyRead]


class CommunitySurfaceRead(ModelBase):
    key: str
    label: str
    path: str
    enabled: bool


class CommunityConfigRead(ModelBase):
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


class ResumeSkillGroupRead(ModelBase):
    category: str
    items: list[str]
    order_index: int


class ResumeExperienceRead(ModelBase):
    title: str
    company: str
    period: str
    summary: str
    order_index: int


class ResumeRead(ModelBase):
    title: str
    subtitle: str
    summary: str
    download_label: str
    skill_groups: list[ResumeSkillGroupRead]
    experiences: list[ResumeExperienceRead]

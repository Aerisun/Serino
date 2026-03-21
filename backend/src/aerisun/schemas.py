from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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


class SiteConfigRead(ModelBase):
    site: SiteProfileRead
    social_links: list[SocialLinkRead]
    poems: list[PoemRead]


class PageCopyRead(ModelBase):
    page_key: str
    label: str | None
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


class ContentEntryRead(ModelBase):
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


class ContentCollectionRead(ModelBase):
    items: list[ContentEntryRead]


class HealthRead(ModelBase):
    status: str
    database_path: str
    timestamp: datetime

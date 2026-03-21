from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    author: str
    og_image: str
    meta_description: str
    copyright: str
    hero_actions: list[dict[str, object]]


class SiteConfigRead(ModelBase):
    site: SiteProfileRead
    social_links: list[SocialLinkRead]
    poems: list[PoemRead]


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


class FriendRead(ModelBase):
    name: str
    description: str | None
    avatar: str | None
    url: str
    status: str
    order_index: int


class FriendCollectionRead(ModelBase):
    items: list[FriendRead]


class FriendFeedItemRead(ModelBase):
    title: str
    summary: str | None
    url: str
    blogName: str
    avatar: str | None
    publishedAt: datetime | None


class FriendFeedCollectionRead(ModelBase):
    items: list[FriendFeedItemRead]


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


class GuestbookEntryRead(ModelBase):
    id: str
    name: str
    website: str | None
    body: str
    status: str
    created_at: datetime


class GuestbookCreate(ModelBase):
    name: str
    email: str | None = None
    website: str | None = None
    body: str


class GuestbookCollectionRead(ModelBase):
    items: list[GuestbookEntryRead]


class GuestbookCreateResponse(ModelBase):
    item: GuestbookEntryRead
    accepted: bool


class CommentRead(ModelBase):
    id: str
    parent_id: str | None
    author_name: str
    body: str
    status: str
    created_at: datetime
    replies: list["CommentRead"] = Field(default_factory=list)


class CommentCollectionRead(ModelBase):
    items: list[CommentRead]


class CommentCreate(ModelBase):
    author_name: str
    author_email: str | None = None
    body: str
    parent_id: str | None = None


class CommentCreateResponse(ModelBase):
    item: CommentRead
    accepted: bool


class ReactionCreate(ModelBase):
    content_type: str
    content_slug: str
    reaction_type: str
    client_token: str | None = None


class ReactionRead(ModelBase):
    content_type: str
    content_slug: str
    reaction_type: str
    total: int


class CalendarEventRead(ModelBase):
    date: str
    type: str
    title: str
    slug: str
    href: str


class CalendarRead(ModelBase):
    range_start: str
    range_end: str
    events: list[CalendarEventRead]


class RecentActivityItemRead(ModelBase):
    kind: str
    actor_name: str
    actor_avatar: str
    target_title: str
    excerpt: str | None
    created_at: datetime
    href: str


class RecentActivityRead(ModelBase):
    items: list[RecentActivityItemRead]


class ActivityHeatmapStatsRead(ModelBase):
    total_contributions: int
    peak_week: int
    average_per_week: int


class ActivityHeatmapWeekRead(ModelBase):
    week_start: str
    total: int
    days: list[int]
    month_label: str
    label: str


class ActivityHeatmapRead(ModelBase):
    stats: ActivityHeatmapStatsRead
    weeks: list[ActivityHeatmapWeekRead]


class HealthRead(ModelBase):
    status: str
    database_path: str
    timestamp: datetime


CommentRead.model_rebuild()

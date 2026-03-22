from __future__ import annotations

from datetime import datetime

from aerisun.core.schemas import ModelBase


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
    category: str | None = None
    read_time: str | None = None
    display_date: str | None = None
    relative_date: str | None = None
    view_count: int | None = None
    comment_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None
    mood: str | None = None
    weather: str | None = None
    poem: str | None = None
    author: str | None = None
    source: str | None = None


class ContentCollectionRead(ModelBase):
    items: list[ContentEntryRead]

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from aerisun.core.schemas import ModelBase


class ContentEntryRead(ModelBase):
    slug: str = Field(description="URL-friendly unique identifier")
    title: str = Field(description="Content display title")
    summary: str | None = Field(description="Brief summary or excerpt")
    body: str = Field(description="Full content body in Markdown")
    tags: list[str] = Field(description="List of tag names")
    status: str = Field(description="Publication status")
    visibility: str = Field(description="Visibility level")
    published_at: datetime | None = Field(description="Publication timestamp")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    category: str | None = Field(default=None, description="Content category")
    read_time: str | None = Field(default=None, description="Estimated reading time")
    display_date: str | None = Field(default=None, description="Formatted display date string")
    relative_date: str | None = Field(default=None, description="Relative time string (e.g. 3 days ago)")
    view_count: int | None = Field(default=None, description="Total page views")
    comment_count: int | None = Field(default=None, description="Number of comments")
    like_count: int | None = Field(default=None, description="Number of likes")
    repost_count: int | None = Field(default=None, description="Number of reposts")
    mood: str | None = Field(default=None, description="Author mood (diary-specific)")
    weather: str | None = Field(default=None, description="Weather description (diary-specific)")
    poem: str | None = Field(default=None, description="Associated poem text")
    author: str | None = Field(default=None, description="Original author name")
    source: str | None = Field(default=None, description="Source URL or reference")


class ContentCollectionRead(ModelBase):
    items: list[ContentEntryRead] = Field(description="List of content entries")
    total: int = Field(default=0, description="Total number of matching entries")
    has_more: bool = Field(default=False, description="Whether more entries are available")

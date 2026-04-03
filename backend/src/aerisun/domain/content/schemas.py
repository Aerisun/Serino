from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

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


# ---------------------------------------------------------------------------
# Admin Content Schemas
# ---------------------------------------------------------------------------


class ContentCreate(BaseModel):
    slug: str | None = Field(default=None, description="URL-friendly unique identifier")
    title: str | None = Field(default=None, description="Display title")
    summary: str | None = Field(default=None, description="Brief summary or excerpt")
    body: str = Field(description="Full content body in Markdown")
    tags: list[str] = Field(default_factory=list, description="List of tag names")
    status: Literal["draft", "published", "archived"] = Field(
        default="draft",
        description="Publication status: draft, public publish, or private archive",
    )
    visibility: Literal["public", "private"] = Field(
        default="public",
        description="Visibility level: public or private",
    )
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
    status: Literal["draft", "published", "archived"] | None = Field(default=None, description="Publication status")
    visibility: Literal["public", "private"] | None = Field(default=None, description="Visibility level")
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


class PoemGenerationRequest(BaseModel):
    body: str = Field(description="日记 Markdown 草稿内容")
    title: str | None = Field(default=None, description="当前标题")
    summary: str | None = Field(default=None, description="当前摘要")
    tags: list[str] | None = Field(default=None, description="标签列表")
    mood: str | None = Field(default=None, description="心情 emoji 或说明")
    weather: str | None = Field(default=None, description="天气")
    custom_requirement: str | None = Field(default=None, description="用户补充的定制要求")


class PoemGenerationResponse(BaseModel):
    poem: str = Field(description="生成的诗句")


# Search
class SearchResultItem(BaseModel):
    type: str = Field(description="Content type")
    slug: str = Field(description="URL-friendly identifier")
    title: str = Field(description="Content title")
    snippet: str = Field(description="Matched text snippet")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")


class SearchResponse(BaseModel):
    items: list[SearchResultItem] = Field(description="Search result items")
    total: int = Field(description="Total matching results")


# Content metadata
class TagInfo(BaseModel):
    name: str = Field(description="Tag name")
    count: int = Field(description="Number of entries with this tag")


class ContentCategoryRead(ModelBase):
    id: str = Field(description="Category identifier")
    content_type: str = Field(description="Content type bucket")
    name: str = Field(description="Category name")
    usage_count: int = Field(default=0, description="How many entries use this category")


class ContentCategoryCreate(BaseModel):
    content_type: Literal["posts", "thoughts", "excerpts"] = Field(
        description="Content type bucket",
    )
    name: str = Field(min_length=1, max_length=80, description="Category name")


class ContentCategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Category name")


# Import/Export
class ImportResult(BaseModel):
    created: int = Field(default=0, description="Number of entries created")
    updated: int = Field(default=0, description="Number of entries updated")
    errors: list[str] = Field(default_factory=list, description="Error messages")

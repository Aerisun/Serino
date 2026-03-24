from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class FriendRead(ModelBase):
    name: str = Field(description="Friend site name")
    description: str | None = Field(description="Short description")
    avatar: str | None = Field(description="Avatar image URL")
    url: str = Field(description="Friend site URL")
    status: str = Field(description="Link status")
    order_index: int = Field(description="Display order")


class FriendCollectionRead(ModelBase):
    items: list[FriendRead] = Field(description="List of friend links")


class FriendFeedItemRead(ModelBase):
    title: str = Field(description="Feed item title")
    summary: str | None = Field(description="Feed item summary")
    url: str = Field(description="Feed item URL")
    blogName: str = Field(description="Source blog name")
    avatar: str | None = Field(description="Source blog avatar")
    publishedAt: datetime | None = Field(description="Publication timestamp")


class FriendFeedCollectionRead(ModelBase):
    items: list[FriendFeedItemRead] = Field(description="List of friend feed items")


# ---------------------------------------------------------------------------
# Admin: Friend
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


# ---------------------------------------------------------------------------
# Admin: FriendFeedSource
# ---------------------------------------------------------------------------


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

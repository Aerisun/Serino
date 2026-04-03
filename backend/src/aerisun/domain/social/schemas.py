from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from aerisun.core.schemas import ModelBase


class FriendRead(ModelBase):
    name: str = Field(description="Friend site name")
    description: str | None = Field(description="Short description")
    avatar: str | None = Field(description="Avatar image URL")
    url: str = Field(description="Friend site URL")
    status: str = Field(description="Website status")


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
    status: str = Field(default="active", description="Website status: active, lost, or archived")

    @field_validator("name", "url", "avatar_url", "description", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name", "url")
    @classmethod
    def _validate_required_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("field cannot be blank")
        return value

    @field_validator("avatar_url", "description")
    @classmethod
    def _blank_optional_to_none(cls, value: str | None) -> str | None:
        return value or None


class FriendUpdate(BaseModel):
    name: str | None = Field(default=None, description="Friend site display name")
    url: str | None = Field(default=None, description="Friend site URL")
    avatar_url: str | None = Field(default=None, description="Avatar image URL")
    description: str | None = Field(default=None, description="Short description")
    status: str | None = Field(default=None, description="Website status")

    @field_validator("name", "url", "avatar_url", "description", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name", "url")
    @classmethod
    def _validate_optional_required_non_empty(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("field cannot be blank")
        return value

    @field_validator("avatar_url", "description")
    @classmethod
    def _blank_optional_to_none(cls, value: str | None) -> str | None:
        return value or None


class FriendAdminRead(ModelBase):
    id: str = Field(description="Unique friend identifier")
    name: str = Field(description="Friend site display name")
    url: str = Field(description="Friend site URL")
    avatar_url: str | None = Field(description="Avatar image URL")
    description: str | None = Field(description="Short description")
    status: str = Field(description="Website status")
    rss_status: str = Field(description="RSS status derived from the configured feed sources")
    last_checked_at: datetime | None = Field(description="Last website availability check timestamp")
    last_error: str | None = Field(description="Last website availability error message")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Admin: FriendFeedSource
# ---------------------------------------------------------------------------


class FriendFeedSourceCreate(BaseModel):
    friend_id: str = Field(description="Associated friend ID")
    feed_url: str = Field(description="RSS/Atom feed URL")
    is_enabled: bool = Field(default=True, description="Whether to actively crawl this feed")

    @field_validator("friend_id", "feed_url", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("friend_id", "feed_url")
    @classmethod
    def _validate_required_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("field cannot be blank")
        return value


class FriendFeedSourceUpdate(BaseModel):
    feed_url: str | None = Field(default=None, description="RSS/Atom feed URL")
    is_enabled: bool | None = Field(default=None, description="Whether to actively crawl")

    @field_validator("feed_url", mode="before")
    @classmethod
    def _strip_feed_url(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("feed_url")
    @classmethod
    def _validate_feed_url_non_empty(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("feed_url cannot be blank")
        return value


class FriendFeedSourceAdminRead(ModelBase):
    id: str = Field(description="Unique feed source identifier")
    friend_id: str = Field(description="Associated friend ID")
    feed_url: str = Field(description="RSS/Atom feed URL")
    last_fetched_at: datetime | None = Field(description="Last RSS fetch/check timestamp")
    is_enabled: bool = Field(description="Whether actively crawled")
    rss_status: str = Field(description="Current RSS status for this source")
    etag: str | None = Field(default=None, description="HTTP ETag for conditional requests")
    last_error: str | None = Field(default=None, description="Last crawl error message")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

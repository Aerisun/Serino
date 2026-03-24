from __future__ import annotations

from datetime import datetime

from pydantic import Field

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

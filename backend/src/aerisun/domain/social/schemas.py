from __future__ import annotations

from datetime import datetime

from aerisun.core.schemas import ModelBase


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

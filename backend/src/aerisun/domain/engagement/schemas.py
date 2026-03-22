from __future__ import annotations

from datetime import datetime

from pydantic import Field

from aerisun.core.schemas import ModelBase


class GuestbookEntryRead(ModelBase):
    id: str
    name: str
    website: str | None
    body: str
    status: str
    created_at: datetime
    avatar: str | None = None
    avatar_url: str | None = None


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
    avatar: str | None = None
    avatar_url: str | None = None
    like_count: int = 0
    liked: bool = False
    is_author: bool = False
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


CommentRead.model_rebuild()

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from aerisun.core.schemas import ModelBase


class GuestbookEntryRead(ModelBase):
    id: str = Field(description="Unique guestbook entry identifier")
    name: str = Field(description="Guest display name")
    website: str | None = Field(description="Guest personal website URL")
    body: str = Field(description="Guestbook message body")
    status: str = Field(description="Moderation status")
    created_at: datetime = Field(description="Entry creation timestamp")
    avatar: str | None = Field(default=None, description="Avatar identifier or key")
    avatar_url: str | None = Field(default=None, description="Full avatar image URL")
    is_author: bool = Field(default=False, description="Whether the guestbook author is the site owner")


class GuestbookCreate(ModelBase):
    name: str = Field(description="Guest display name")
    email: str | None = Field(default=None, description="Guest email address")
    website: str | None = Field(default=None, description="Guest personal website URL")
    body: str = Field(description="Guestbook message body")
    avatar_key: str | None = Field(default=None, description="Selected guest avatar preset key")
    auth_token: str | None = Field(default=None, description="Waline login token for authenticated posting")


class GuestbookCollectionRead(ModelBase):
    items: list[GuestbookEntryRead] = Field(description="List of guestbook entries")
    total: int = Field(description="Total number of public guestbook entries")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of guestbook entries per page")
    has_more: bool = Field(description="Whether more guestbook entries can be loaded")


class GuestbookCreateResponse(ModelBase):
    item: GuestbookEntryRead = Field(description="Created guestbook entry")
    accepted: bool = Field(description="Whether the entry was auto-approved")


class CommentRead(ModelBase):
    id: str = Field(description="Unique comment identifier")
    parent_id: str | None = Field(description="Parent comment ID for threaded replies")
    author_name: str = Field(description="Comment author display name")
    body: str = Field(description="Comment body text")
    status: str = Field(description="Moderation status")
    created_at: datetime = Field(description="Comment creation timestamp")
    avatar: str | None = Field(default=None, description="Avatar identifier or key")
    avatar_url: str | None = Field(default=None, description="Full avatar image URL")
    like_count: int = Field(default=0, description="Number of likes on this comment")
    liked: bool = Field(default=False, description="Whether the current user liked this comment")
    is_author: bool = Field(default=False, description="Whether the commenter is the content author")
    replies: list[CommentRead] = Field(default_factory=list, description="Nested reply comments")


class CommentCollectionRead(ModelBase):
    items: list[CommentRead] = Field(description="List of comments")
    total: int = Field(description="Total number of root comment threads")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of root comment threads per page")
    has_more: bool = Field(description="Whether more root comment threads can be loaded")


class CommentCreate(ModelBase):
    author_name: str = Field(description="Comment author display name")
    author_email: str | None = Field(default=None, description="Comment author email address")
    body: str = Field(description="Comment body text")
    parent_id: str | None = Field(default=None, description="Parent comment ID for replies")
    avatar_key: str | None = Field(default=None, description="Selected comment avatar preset key")
    auth_token: str | None = Field(default=None, description="Waline login token for authenticated posting")


class CommentCreateResponse(ModelBase):
    item: CommentRead = Field(description="Created comment")
    accepted: bool = Field(description="Whether the comment was auto-approved")


class ReactionCreate(ModelBase):
    content_type: str = Field(description="Content type: posts, diary, thoughts, or excerpts")
    content_slug: str = Field(description="Slug of the content to react to")
    reaction_type: str = Field(description="Reaction type identifier (e.g. like)")
    client_token: str | None = Field(default=None, description="Client-side deduplication token")


class ReactionRead(ModelBase):
    content_type: str = Field(description="Content type")
    content_slug: str = Field(description="Content slug")
    reaction_type: str = Field(description="Reaction type identifier")
    total: int = Field(description="Total reaction count")


CommentRead.model_rebuild()

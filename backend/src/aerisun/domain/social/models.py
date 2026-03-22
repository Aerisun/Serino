from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class Friend(Base, TimestampMixin):
    __tablename__ = "friends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FriendFeedSource(Base, TimestampMixin):
    __tablename__ = "friend_feed_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    friend_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("friends.id", ondelete="CASCADE"),
        nullable=False,
    )
    feed_url: Mapped[str] = mapped_column(String(500), nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    etag: Mapped[str | None] = mapped_column(String(500))
    last_error: Mapped[str | None] = mapped_column(Text)


class FriendFeedItem(Base, TimestampMixin):
    __tablename__ = "friend_feed_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("friend_feed_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

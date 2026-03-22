from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class GuestbookEntry(Base, TimestampMixin):
    __tablename__ = "guestbook_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("comments.id", ondelete="SET NULL"),
    )
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)
    author_email: Mapped[str | None] = mapped_column(String(320))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


class Reaction(Base, TimestampMixin):
    __tablename__ = "reactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    reaction_type: Mapped[str] = mapped_column(String(80), nullable=False)
    client_token: Mapped[str | None] = mapped_column(String(160))

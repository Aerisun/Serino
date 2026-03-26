from __future__ import annotations

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, ContentMixin, TimestampMixin


class ContentCategory(Base, TimestampMixin):
    __tablename__ = "content_categories"
    __table_args__ = (
        UniqueConstraint("content_type", "name", name="uq_content_categories_type_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


class PostEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "posts"

    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DiaryEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "diary_entries"

    mood: Mapped[str | None] = mapped_column(String(40), nullable=True)
    weather: Mapped[str | None] = mapped_column(String(40), nullable=True)
    poem: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ThoughtEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "thoughts"

    mood: Mapped[str | None] = mapped_column(String(40), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExcerptEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "excerpts"

    author_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

from __future__ import annotations

from aerisun.core.base import Base, ContentMixin, TimestampMixin


class PostEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "posts"


class DiaryEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "diary_entries"


class ThoughtEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "thoughts"


class ExcerptEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "excerpts"

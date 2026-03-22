from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class SiteProfile(Base, TimestampMixin):
    __tablename__ = "site_profile"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(160), nullable=False)
    footer_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    og_image: Mapped[str] = mapped_column(String(500), nullable=False, default="/images/hero_bg.jpeg")
    meta_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    copyright: Mapped[str] = mapped_column(String(200), nullable=False, default="All rights reserved")
    hero_actions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hero_video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class NavItem(Base, TimestampMixin):
    __tablename__ = "nav_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    site_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("nav_items.id", ondelete="CASCADE"),
        nullable=True,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    href: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    page_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SocialLink(Base, TimestampMixin):
    __tablename__ = "social_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    site_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    href: Mapped[str] = mapped_column(String(500), nullable=False)
    icon_key: Mapped[str] = mapped_column(String(80), nullable=False)
    placement: Mapped[str] = mapped_column(String(40), nullable=False, default="hero")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Poem(Base, TimestampMixin):
    __tablename__ = "poems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    site_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class PageCopy(Base, TimestampMixin):
    __tablename__ = "page_copy"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    page_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nav_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    subtitle: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_placeholder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    empty_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_width: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    extras: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PageDisplayOption(Base, TimestampMixin):
    __tablename__ = "page_display_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    page_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CommunityConfig(Base, TimestampMixin):
    __tablename__ = "community_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, default="waline")
    server_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    surfaces: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    meta: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_meta: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    emoji_presets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    enable_enjoy_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    image_uploader: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    login_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="disable")
    oauth_url: Mapped[str | None] = mapped_column(String(500))
    avatar_strategy: Mapped[str] = mapped_column(String(80), nullable=False, default="identicon")
    avatar_helper_copy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    migration_state: Mapped[str] = mapped_column(String(40), nullable=False, default="not_started")


class ResumeBasics(Base, TimestampMixin):
    __tablename__ = "resume_basics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    download_label: Mapped[str] = mapped_column(String(80), nullable=False)


class ResumeSkillGroup(Base, TimestampMixin):
    __tablename__ = "resume_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    resume_basics_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_basics.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    items: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ResumeExperience(Base, TimestampMixin):
    __tablename__ = "resume_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    resume_basics_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_basics.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    company: Mapped[str] = mapped_column(String(160), nullable=False)
    period: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ContentMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostEntry(ContentMixin, Base, TimestampMixin):
    __tablename__ = "posts"
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
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


class ModerationRecord(Base, TimestampMixin):
    __tablename__ = "moderation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


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


class SyncRun(Base, TimestampMixin):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(128))


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AdminSession(Base, TimestampMixin):
    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    admin_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    key_name: Mapped[str] = mapped_column(String(160), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    hashed_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BackupSnapshot(Base, TimestampMixin):
    __tablename__ = "backup_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    snapshot_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    db_path: Mapped[str] = mapped_column(String(500), nullable=False)
    replica_url: Mapped[str | None] = mapped_column(String(500))
    backup_path: Mapped[str | None] = mapped_column(String(500))
    checksum: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RestorePoint(Base, TimestampMixin):
    __tablename__ = "restore_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    snapshot_id: Mapped[str | None] = mapped_column(String(36))
    db_path: Mapped[str] = mapped_column(String(500), nullable=False)
    point_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

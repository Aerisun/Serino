from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


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
    oauth_providers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    anonymous_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    moderation_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="all_pending")
    default_sorting: Mapped[str] = mapped_column(String(40), nullable=False, default="latest")
    page_size: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    avatar_presets: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    guest_avatar_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="preset")
    draft_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

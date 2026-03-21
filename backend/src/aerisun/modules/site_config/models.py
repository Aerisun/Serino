from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aerisun.shared.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SiteProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "site_profiles"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(160), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    og_image: Mapped[str] = mapped_column(String(255), nullable=False)
    footer_text: Mapped[str] = mapped_column(String(255), nullable=False, default="用 ♥ 与代码构建")

    social_links: Mapped[list["SocialLink"]] = relationship(back_populates="site_profile", cascade="all, delete-orphan")
    poems: Mapped[list["Poem"]] = relationship(back_populates="site_profile", cascade="all, delete-orphan")
    page_copies: Mapped[list["PageCopy"]] = relationship(back_populates="site_profile", cascade="all, delete-orphan")
    page_display_options: Mapped[list["PageDisplayOption"]] = relationship(
        back_populates="site_profile",
        cascade="all, delete-orphan",
    )
    resume_basic: Mapped["ResumeBasic | None"] = relationship(back_populates="site_profile", uselist=False)
    resume_skills: Mapped[list["ResumeSkill"]] = relationship(back_populates="site_profile", cascade="all, delete-orphan")
    resume_experiences: Mapped[list["ResumeExperience"]] = relationship(
        back_populates="site_profile",
        cascade="all, delete-orphan",
    )


class SocialLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "social_links"

    site_profile_id: Mapped[str] = mapped_column(ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    href: Mapped[str] = mapped_column(String(255), nullable=False)
    icon_key: Mapped[str] = mapped_column(String(64), nullable=False)
    placements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    site_profile: Mapped[SiteProfile] = relationship(back_populates="social_links")


class Poem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "poems"

    site_profile_id: Mapped[str] = mapped_column(ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    site_profile: Mapped[SiteProfile] = relationship(back_populates="poems")


class PageCopy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "page_copies"

    site_profile_id: Mapped[str] = mapped_column(ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    page_key: Mapped[str] = mapped_column(String(64), nullable=False)
    eyebrow: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_placeholder: Mapped[str | None] = mapped_column(String(160), nullable=True)
    empty_message: Mapped[str | None] = mapped_column(String(160), nullable=True)
    all_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    circle_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    download_label: Mapped[str | None] = mapped_column(String(80), nullable=True)

    site_profile: Mapped[SiteProfile] = relationship(back_populates="page_copies")


class PageDisplayOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "page_display_options"

    site_profile_id: Mapped[str] = mapped_column(ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    page_key: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[str] = mapped_column(String(32), nullable=False, default="content")
    page_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    show_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_filters: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    site_profile: Mapped[SiteProfile] = relationship(back_populates="page_display_options")


class ResumeBasic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resume_basics"

    site_profile_id: Mapped[str] = mapped_column(
        ForeignKey("site_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meta_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_label: Mapped[str] = mapped_column(String(80), nullable=False, default="下载 PDF")

    site_profile: Mapped[SiteProfile] = relationship(back_populates="resume_basic")


class ResumeSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resume_skills"

    site_profile_id: Mapped[str] = mapped_column(ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    site_profile: Mapped[SiteProfile] = relationship(back_populates="resume_skills")


class ResumeExperience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resume_experiences"

    site_profile_id: Mapped[str] = mapped_column(ForeignKey("site_profiles.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(160), nullable=False)
    organization: Mapped[str] = mapped_column(String(160), nullable=False)
    period: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    site_profile: Mapped[SiteProfile] = relationship(back_populates="resume_experiences")


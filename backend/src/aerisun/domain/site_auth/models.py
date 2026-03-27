from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class SiteAuthConfig(Base, TimestampMixin):
    __tablename__ = "site_auth_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email_login_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    visitor_oauth_providers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    admin_auth_methods: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    admin_email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    google_client_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    google_client_secret: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    github_client_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    github_client_secret: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class SiteUser(Base, TimestampMixin):
    __tablename__ = "site_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    primary_auth_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="email")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SiteUserOAuthAccount(Base, TimestampMixin):
    __tablename__ = "site_user_oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_site_user_oauth_provider_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    site_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SiteAdminIdentity(Base, TimestampMixin):
    __tablename__ = "site_admin_identities"
    __table_args__ = (UniqueConstraint("provider", "identifier", name="uq_site_admin_identity_provider_identifier"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    site_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    admin_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    provider_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)


class SiteUserSession(Base, TimestampMixin):
    __tablename__ = "site_user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    site_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class ContentSubscriptionConfig(Base, TimestampMixin):
    __tablename__ = "content_subscription_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_auth_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="password")
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_oauth_tenant: Mapped[str] = mapped_column(String(120), nullable=False, default="common")
    smtp_oauth_client_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_oauth_client_secret: Mapped[str] = mapped_column(Text, nullable=False, default="")
    smtp_oauth_refresh_token: Mapped[str] = mapped_column(Text, nullable=False, default="")
    smtp_from_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_from_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    smtp_reply_to: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_test_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allowed_content_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    mail_subject_template: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="[{site_name}] {content_title}",
    )
    mail_body_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            "{site_name} 有新的{content_type_label}内容发布。\n\n"
            "{content_title}\n"
            "{content_summary}\n\n"
            "阅读链接：{content_url}\n"
            "RSS：{feed_url}"
        ),
    )


class ContentSubscriber(Base, TimestampMixin):
    __tablename__ = "content_subscribers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContentNotification(Base, TimestampMixin):
    __tablename__ = "content_notifications"
    __table_args__ = (UniqueConstraint("content_type", "content_slug", name="uq_content_notifications_type_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    content_title: Mapped[str] = mapped_column(String(240), nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_url: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentNotificationDelivery(Base, TimestampMixin):
    __tablename__ = "content_notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    notification_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subscriber_email: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    content_title: Mapped[str] = mapped_column(String(240), nullable=False)
    content_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="sent")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

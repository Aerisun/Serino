from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, desc
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class PostAccessRequest(Base, TimestampMixin):
    __tablename__ = "post_access_requests"
    __table_args__ = (
        Index(
            "ix_post_access_requests_post_user_created_id",
            "post_id",
            "site_user_id",
            desc("created_at"),
            desc("id"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    post_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("site_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )

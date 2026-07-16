from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, desc
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class DiaryAccessRequest(Base, TimestampMixin):
    __tablename__ = "diary_access_requests"
    __table_args__ = (
        Index(
            "ix_diary_access_requests_site_user_created_id",
            "site_user_id",
            desc("created_at"),
            desc("id"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
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

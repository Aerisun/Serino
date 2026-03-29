from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, utcnow, uuid_str


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ConfigRevision(Base):
    __tablename__ = "config_revisions"
    __table_args__ = (
        Index("ix_config_revisions_resource_key_created_at", "resource_key", "created_at"),
        Index("ix_config_revisions_actor_id_created_at", "actor_id", "created_at"),
        Index("ix_config_revisions_restored_from_revision_id", "restored_from_revision_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    resource_key: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_label: Mapped[str] = mapped_column(String(160), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_version: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changed_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    before_snapshot: Mapped[Any] = mapped_column(JSON, nullable=True)
    after_snapshot: Mapped[Any] = mapped_column(JSON, nullable=True)
    before_preview: Mapped[Any] = mapped_column(JSON, nullable=True)
    after_preview: Mapped[Any] = mapped_column(JSON, nullable=True)
    sensitive_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    restored_from_revision_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ModerationRecord(Base, TimestampMixin):
    __tablename__ = "moderation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


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


class SyncRun(Base, TimestampMixin):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)


class TrafficDailySnapshot(Base, TimestampMixin):
    __tablename__ = "traffic_daily_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", "url", name="uq_traffic_daily_snapshots_date_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    snapshot_date: Mapped[date] = mapped_column(Date(), nullable=False)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    cumulative_views: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    daily_views: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    cumulative_reactions: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)


class VisitRecord(Base, TimestampMixin):
    __tablename__ = "visit_records"
    __table_args__ = (
        Index("ix_visit_records_visited_at", "visited_at"),
        Index("ix_visit_records_path_visited_at", "path", "visited_at"),
        Index("ix_visit_records_ip_address_visited_at", "ip_address", "visited_at"),
        Index("ix_visit_records_is_bot", "is_bot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    referer: Mapped[str | None] = mapped_column(String(500))
    status_code: Mapped[int] = mapped_column(Integer(), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    is_bot: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)

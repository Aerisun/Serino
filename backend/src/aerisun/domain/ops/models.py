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


class SyncRun(Base, TimestampMixin):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    transport: Mapped[str | None] = mapped_column(String(32))
    trigger_kind: Mapped[str | None] = mapped_column(String(32))
    queue_item_id: Mapped[str | None] = mapped_column(String(36))
    commit_id: Mapped[str | None] = mapped_column(String(36))
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)


class BackupTargetConfig(Base, TimestampMixin):
    __tablename__ = "backup_target_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    paused: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer(), nullable=False, default=60)
    transport_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="sftp")
    site_slug: Mapped[str] = mapped_column(String(120), nullable=False, default="aerisun")
    remote_host: Mapped[str | None] = mapped_column(String(255))
    remote_port: Mapped[int | None] = mapped_column(Integer())
    remote_path: Mapped[str | None] = mapped_column(String(500))
    remote_username: Mapped[str | None] = mapped_column(String(255))
    credential_ref: Mapped[str | None] = mapped_column(String(255))
    encrypt_runtime_data: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    max_retries: Mapped[int] = mapped_column(Integer(), nullable=False, default=3)
    retry_backoff_seconds: Mapped[int] = mapped_column(Integer(), nullable=False, default=300)
    max_retention_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    last_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class BackupQueueItem(Base, TimestampMixin):
    __tablename__ = "backup_queue_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    dataset_versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    verified_chunks: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackupCommit(Base, TimestampMixin):
    __tablename__ = "backup_commits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    site_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    remote_commit_id: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    backup_path: Mapped[str | None] = mapped_column(String(500))
    datasets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackupRecoveryKey(Base, TimestampMixin):
    __tablename__ = "backup_recovery_keys"
    __table_args__ = (
        Index("ix_backup_recovery_keys_credential_status", "credential_ref", "status", "created_at"),
        Index("ix_backup_recovery_keys_fingerprint", "secrets_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    credential_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    site_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    secrets_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    secrets_public_pem: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_private_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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

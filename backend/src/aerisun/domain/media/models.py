from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, utcnow, uuid_str


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    note: Mapped[str | None] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(128))
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    remote_object_key: Mapped[str | None] = mapped_column(String(500))
    remote_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    remote_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remote_etag: Mapped[str | None] = mapped_column(String(255))
    mirror_status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    mirror_last_error: Mapped[str | None] = mapped_column(Text)
    oss_acceleration_enabled_at_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ObjectStorageConfig(Base, TimestampMixin):
    __tablename__ = "object_storage_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="bitiful")
    bucket: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    region: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    public_base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    access_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    secret_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cdn_token_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    health_check_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    upload_expire_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    public_download_expire_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    mirror_bandwidth_limit_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=2 * 1024 * 1024)
    mirror_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_health_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_health_error: Mapped[str | None] = mapped_column(Text)
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssetMirrorQueueItem(Base, TimestampMixin):
    __tablename__ = "asset_mirror_queue_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    asset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssetRemoteDeleteQueueItem(Base, TimestampMixin):
    __tablename__ = "asset_remote_delete_queue_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

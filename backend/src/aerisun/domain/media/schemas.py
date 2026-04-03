from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class AssetAdminRead(ModelBase):
    id: str
    file_name: str
    resource_key: str
    visibility: Literal["internal", "public"]
    scope: Literal["system", "user"]
    category: str
    note: str | None
    storage_path: str
    internal_url: str
    public_url: str | None
    mime_type: str | None
    byte_size: int | None
    sha256: str | None
    storage_provider: str
    remote_status: str
    mirror_status: str
    mirror_last_error: str | None
    oss_acceleration_enabled_at_upload: bool
    created_at: datetime
    updated_at: datetime


class AssetAdminUpdate(ModelBase):
    visibility: Literal["internal", "public"] | None = None
    scope: Literal["system", "user"] | None = None
    category: str | None = None
    note: str | None = None


class AssetUploadPlanWrite(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(ge=1)
    sha256: str = Field(min_length=32, max_length=128)
    mime_type: str | None = Field(default=None, max_length=120)
    visibility: Literal["internal", "public"] = "internal"
    scope: Literal["system", "user"] = "user"
    category: str = Field(default="general", max_length=80)
    note: str | None = Field(default=None, max_length=500)


class AssetUploadPlanRead(ModelBase):
    mode: Literal["local", "oss", "existing"]
    asset_id: str | None = None
    resource_key: str | None = None
    upload_url: str | None = None
    upload_method: Literal["PUT"] | None = None
    upload_headers: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime | None = None
    asset: AssetAdminRead | None = None


class AssetUploadCompleteWrite(BaseModel):
    asset_id: str


class ObjectStorageConfigRead(ModelBase):
    enabled: bool
    provider: Literal["bitiful"]
    bucket: str
    endpoint: str
    region: str
    public_base_url: str
    access_key: str
    secret_key_configured: bool
    cdn_token_key_configured: bool
    health_check_enabled: bool
    upload_expire_seconds: int
    public_download_expire_seconds: int
    mirror_bandwidth_limit_bps: int
    mirror_retry_count: int
    last_health_ok: bool | None = None
    last_health_error: str | None = None
    last_health_checked_at: datetime | None = None


class ObjectStorageConfigUpdate(BaseModel):
    enabled: bool | None = None
    provider: Literal["bitiful"] | None = None
    bucket: str | None = Field(default=None, max_length=255)
    endpoint: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=120)
    public_base_url: str | None = Field(default=None, max_length=500)
    access_key: str | None = Field(default=None, max_length=255)
    secret_key: str | None = Field(default=None, max_length=5000)
    cdn_token_key: str | None = Field(default=None, max_length=5000)
    health_check_enabled: bool | None = None
    upload_expire_seconds: int | None = Field(default=None, ge=30, le=3600)
    public_download_expire_seconds: int | None = Field(default=None, ge=30, le=3600)
    mirror_bandwidth_limit_bps: int | None = Field(default=None, ge=64 * 1024, le=128 * 1024 * 1024)
    mirror_retry_count: int | None = Field(default=None, ge=0, le=10)


class ObjectStorageHealthRead(ModelBase):
    ok: bool
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)

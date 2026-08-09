from __future__ import annotations

import hashlib
import logging
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from sqlalchemy.orm import Session

from aerisun.core.base import utcnow
from aerisun.core.data_storage_lock import data_storage_cleanup_pending, data_storage_locked
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.core.time import normalize_shanghai_datetime
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.media import repository as repo
from aerisun.domain.media.models import (
    Asset,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
    ObjectStorageConfig,
)
from aerisun.domain.media.paths import (
    assert_managed_local_path,
    build_local_path,
    build_remote_object_key,
    identity_from_resource_key,
)
from aerisun.domain.media.schemas import (
    AssetAdminRead,
    ObjectStorageConfigRead,
    ObjectStorageConfigUpdate,
    ObjectStorageHealthRead,
    ObjectStorageSyncRecordRead,
)

logger = logging.getLogger(__name__)

DEFAULT_OBJECT_STORAGE_CONFIG = {
    "enabled": False,
    "provider": "bitiful",
    "bucket": "",
    "endpoint": "",
    "region": "",
    "public_base_url": "",
    "access_key": "",
    "secret_key": "",
    "cdn_token_key": "",
    "health_check_enabled": True,
    "upload_expire_seconds": 300,
    "public_download_expire_seconds": 600,
    "mirror_bandwidth_limit_bps": 2 * 1024 * 1024,
    "mirror_retry_count": 3,
}
_MIRROR_CHUNK_SIZE = 256 * 1024


class AssetMirrorIntegrityError(RuntimeError):
    """The downloaded OSS object does not match the immutable asset metadata."""


def object_key_for_asset(asset: Asset) -> str:
    identity = identity_from_resource_key(str(asset.resource_key))
    expected = build_remote_object_key(identity, asset.scope)
    existing = str(asset.remote_object_key or "").strip()
    if existing and existing != expected:
        raise ValidationError("资源 OSS Key 与永久标识或范围不一致")
    return expected


@dataclass(slots=True)
class ObjectHead:
    content_length: int | None
    content_type: str | None
    etag: str | None
    last_modified: datetime | None


@dataclass(frozen=True, slots=True)
class ObjectStorageEntry:
    object_key: str
    content_length: int
    etag: str | None


class BitifulObjectStorageProvider:
    def __init__(
        self,
        config: ObjectStorageConfig,
        *,
        connect_timeout_seconds: float | None = None,
        read_timeout_seconds: float | None = None,
        max_attempts: int | None = None,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config as BotoConfig
        except ImportError as exc:  # pragma: no cover - exercised via config fallback
            raise ValidationError("未安装 boto3，无法启用缤纷云 OSS 加速") from exc

        endpoint = str(config.endpoint or "").strip()
        if not endpoint:
            raise ValidationError("缺少 OSS endpoint 配置")

        self._bucket = str(config.bucket or "").strip()
        if not self._bucket:
            raise ValidationError("缺少 OSS bucket 配置")

        boto_config: dict[str, Any] = {"signature_version": "s3v4"}
        if connect_timeout_seconds is not None:
            boto_config["connect_timeout"] = max(float(connect_timeout_seconds), 0.1)
        if read_timeout_seconds is not None:
            boto_config["read_timeout"] = max(float(read_timeout_seconds), 0.1)
        if max_attempts is not None:
            boto_config["retries"] = {
                "total_max_attempts": max(int(max_attempts), 1),
                "mode": "standard",
            }

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=str(config.region or "").strip() or None,
            aws_access_key_id=str(config.access_key or "").strip(),
            aws_secret_access_key=str(config.secret_key or "").strip(),
            config=BotoConfig(**boto_config),
        )

    def sign_upload(self, *, object_key: str, content_type: str | None, expires_in: int) -> str:
        params: dict[str, Any] = {"Bucket": self._bucket, "Key": object_key}
        if content_type:
            params["ContentType"] = content_type
        return str(
            self._client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )
        )

    def sign_download(self, *, object_key: str, expires_in: int) -> str:
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )
        )

    def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None) -> ObjectHead:
        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": object_key,
            "Body": data,
        }
        if content_type:
            params["ContentType"] = content_type
        self._client.put_object(**params)
        return self.head_object(object_key=object_key)

    def upload_local_file(self, *, object_key: str, source_path: Path, content_type: str | None) -> ObjectHead:
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args is None:
            self._client.upload_file(str(source_path), self._bucket, object_key)
        else:
            self._client.upload_file(str(source_path), self._bucket, object_key, ExtraArgs=extra_args)
        return self.head_object(object_key=object_key)

    def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None) -> ObjectHead:
        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": object_key,
            "CopySource": {"Bucket": self._bucket, "Key": source_key},
        }
        if content_type:
            params["ContentType"] = content_type
            params["MetadataDirective"] = "REPLACE"
        self._client.copy_object(**params)
        return self.head_object(object_key=object_key)

    def delete_object(self, *, object_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=object_key)

    def head_object(self, *, object_key: str) -> ObjectHead:
        response = self._client.head_object(Bucket=self._bucket, Key=object_key)
        last_modified = response.get("LastModified")
        if isinstance(last_modified, datetime):
            last_modified = normalize_shanghai_datetime(last_modified)
        return ObjectHead(
            content_length=int(response.get("ContentLength")) if response.get("ContentLength") is not None else None,
            content_type=str(response.get("ContentType") or "").strip() or None,
            etag=str(response.get("ETag") or "").strip().strip('"') or None,
            last_modified=last_modified if isinstance(last_modified, datetime) else None,
        )

    def find_object(self, *, object_key: str) -> ObjectHead | None:
        """Return None only for an authoritative S3 not-found response."""
        try:
            return self.head_object(object_key=object_key)
        except Exception as exc:
            try:
                from botocore.exceptions import ClientError
            except ImportError:  # pragma: no cover - boto3 construction already guards this
                raise
            if not isinstance(exc, ClientError):
                raise
            response = exc.response if isinstance(exc.response, dict) else {}
            error = response.get("Error") if isinstance(response.get("Error"), dict) else {}
            metadata = response.get("ResponseMetadata") if isinstance(response.get("ResponseMetadata"), dict) else {}
            code = str(error.get("Code") or "")
            status = metadata.get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise

    def list_objects(self, *, prefix: str) -> tuple[ObjectStorageEntry, ...]:
        paginator = self._client.get_paginator("list_objects_v2")
        entries: list[ObjectStorageEntry] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for item in page.get("Contents") or ():
                object_key = str(item.get("Key") or "")
                if not object_key:
                    continue
                entries.append(
                    ObjectStorageEntry(
                        object_key=object_key,
                        content_length=int(item.get("Size") or 0),
                        etag=str(item.get("ETag") or "").strip().strip('"') or None,
                    )
                )
        entries.sort(key=lambda item: item.object_key)
        return tuple(entries)

    def download_to_local(
        self,
        *,
        object_key: str,
        dest_path: Path,
        bandwidth_limit_bps: int | None,
    ) -> tuple[int, str | None]:
        response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        body = response["Body"]
        etag = str(response.get("ETag") or "").strip().strip('"') or None
        total = 0
        started_at = time.perf_counter()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as handle:
            while True:
                chunk = body.read(_MIRROR_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                total += len(chunk)
                if bandwidth_limit_bps and bandwidth_limit_bps > 0:
                    elapsed = max(time.perf_counter() - started_at, 0.001)
                    expected_elapsed = total / bandwidth_limit_bps
                    if expected_elapsed > elapsed:
                        time.sleep(expected_elapsed - elapsed)
        return total, etag

    def is_healthy(self) -> ObjectStorageHealthRead:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return ObjectStorageHealthRead(
                ok=True, summary="OSS 配置可用，桶访问正常", details={"bucket": self._bucket}
            )
        except Exception as exc:  # pragma: no cover - exercised via monkeypatch
            return ObjectStorageHealthRead(
                ok=False,
                summary=f"OSS 健康检查失败：{exc}",
                details={"bucket": self._bucket},
            )


def get_or_create_object_storage_config(session: Session) -> ObjectStorageConfig:
    config = repo.get_object_storage_config(session)
    if config is not None:
        return config
    config = repo.create_object_storage_config(session, **DEFAULT_OBJECT_STORAGE_CONFIG)
    session.commit()
    session.refresh(config)
    return config


def _config_to_read(
    config: ObjectStorageConfig,
    *,
    remote_sync_scanned_count: int | None = None,
    remote_sync_enqueued_count: int | None = None,
) -> ObjectStorageConfigRead:
    return ObjectStorageConfigRead(
        enabled=config.enabled,
        provider=str(config.provider or "bitiful").strip() or "bitiful",
        bucket=str(config.bucket or "").strip(),
        endpoint=str(config.endpoint or "").strip(),
        region=str(config.region or "").strip(),
        public_base_url=str(config.public_base_url or "").strip(),
        access_key=str(config.access_key or "").strip(),
        secret_key_configured=bool(str(config.secret_key or "").strip()),
        cdn_token_key_configured=bool(str(config.cdn_token_key or "").strip()),
        health_check_enabled=bool(config.health_check_enabled),
        upload_expire_seconds=int(config.upload_expire_seconds),
        public_download_expire_seconds=int(config.public_download_expire_seconds),
        mirror_bandwidth_limit_bps=int(config.mirror_bandwidth_limit_bps),
        mirror_retry_count=int(config.mirror_retry_count),
        last_health_ok=config.last_health_ok,
        last_health_error=config.last_health_error,
        last_health_checked_at=config.last_health_checked_at,
        remote_sync_scanned_count=remote_sync_scanned_count,
        remote_sync_enqueued_count=remote_sync_enqueued_count,
    )


def get_object_storage_config_read(session: Session) -> ObjectStorageConfigRead:
    return _config_to_read(get_or_create_object_storage_config(session))


@data_storage_locked
def restore_object_storage_config(session: Session, snapshot: dict[str, Any]) -> None:
    if data_storage_cleanup_pending():
        raise StateConflict("资源迁移正在完成旧副本清理，请稍后再恢复 OSS 配置")
    config = get_or_create_object_storage_config(session)
    config.enabled = bool(snapshot.get("enabled", config.enabled))
    config.provider = str(snapshot.get("provider") or config.provider or "bitiful")
    config.bucket = str(snapshot.get("bucket") or "")
    config.endpoint = str(snapshot.get("endpoint") or "")
    config.region = str(snapshot.get("region") or "")
    config.public_base_url = str(snapshot.get("public_base_url") or "")
    config.access_key = str(snapshot.get("access_key") or "")
    config.health_check_enabled = bool(snapshot.get("health_check_enabled", config.health_check_enabled))
    config.upload_expire_seconds = int(snapshot.get("upload_expire_seconds") or config.upload_expire_seconds)
    config.public_download_expire_seconds = int(
        snapshot.get("public_download_expire_seconds") or config.public_download_expire_seconds
    )
    config.mirror_bandwidth_limit_bps = int(
        snapshot.get("mirror_bandwidth_limit_bps") or config.mirror_bandwidth_limit_bps
    )
    config.mirror_retry_count = int(snapshot.get("mirror_retry_count") or config.mirror_retry_count)
    if "secret_key" in snapshot and isinstance(snapshot.get("secret_key"), str):
        config.secret_key = str(snapshot.get("secret_key"))
    if "cdn_token_key" in snapshot and isinstance(snapshot.get("cdn_token_key"), str):
        config.cdn_token_key = str(snapshot.get("cdn_token_key"))
    session.flush()


@data_storage_locked
def update_object_storage_config(session: Session, payload: ObjectStorageConfigUpdate) -> ObjectStorageConfigRead:
    if data_storage_cleanup_pending():
        raise StateConflict("资源迁移正在完成旧副本清理，请稍后再修改 OSS 配置")
    config = get_or_create_object_storage_config(session)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key in {"secret_key", "cdn_token_key"}:
            if value is not None:
                setattr(config, key, str(value).strip())
            continue
        if value is None:
            continue
        setattr(config, key, value)
    session.commit()
    session.refresh(config)
    return _config_to_read(config)


def refresh_object_storage_health_status(session: Session) -> ObjectStorageConfigRead:
    config = get_or_create_object_storage_config(session)
    now = utcnow()
    health = test_object_storage_config(session)
    remote_sync_scanned_count = 0
    remote_sync_enqueued_count = 0

    config.last_health_ok = health.ok
    config.last_health_error = None if health.ok else health.summary
    config.last_health_checked_at = now
    if config.enabled and health.ok:
        remote_sync_scanned_count, remote_sync_enqueued_count = enqueue_missing_remote_assets(session)
    session.commit()
    session.refresh(config)
    return _config_to_read(
        config,
        remote_sync_scanned_count=remote_sync_scanned_count,
        remote_sync_enqueued_count=remote_sync_enqueued_count,
    )


def build_object_storage_provider(session: Session) -> BitifulObjectStorageProvider | None:
    config = get_or_create_object_storage_config(session)
    if not config.enabled:
        return None
    try:
        return BitifulObjectStorageProvider(config)
    except ValidationError as exc:
        logger.warning("Object storage provider unavailable: %s", exc.detail)
        return None


def build_object_storage_maintenance_provider(session: Session) -> BitifulObjectStorageProvider | None:
    config = get_or_create_object_storage_config(session)
    try:
        return BitifulObjectStorageProvider(config)
    except ValidationError as exc:
        logger.warning("Object storage maintenance provider unavailable: %s", exc.detail)
        return None


def test_object_storage_config(
    session: Session,
    payload: ObjectStorageConfigUpdate | None = None,
) -> ObjectStorageHealthRead:
    config = get_or_create_object_storage_config(session)
    snapshot = {
        "enabled": config.enabled,
        "provider": config.provider,
        "bucket": config.bucket,
        "endpoint": config.endpoint,
        "region": config.region,
        "public_base_url": config.public_base_url,
        "access_key": config.access_key,
        "secret_key": config.secret_key,
        "cdn_token_key": config.cdn_token_key,
        "health_check_enabled": config.health_check_enabled,
        "upload_expire_seconds": config.upload_expire_seconds,
        "public_download_expire_seconds": config.public_download_expire_seconds,
        "mirror_bandwidth_limit_bps": config.mirror_bandwidth_limit_bps,
        "mirror_retry_count": config.mirror_retry_count,
    }
    original_secret = config.secret_key
    try:
        if payload is not None:
            for key, value in payload.model_dump(exclude_unset=True).items():
                if key == "secret_key":
                    if value is not None:
                        config.secret_key = str(value).strip()
                    continue
                if key == "cdn_token_key":
                    if value is not None:
                        config.cdn_token_key = str(value).strip()
                    continue
                if value is None:
                    continue
                setattr(config, key, value)
        config.enabled = True
        provider = build_object_storage_provider(session)
        if provider is None:
            health = ObjectStorageHealthRead(ok=False, summary="OSS 配置无效或依赖不可用")
        else:
            health = provider.is_healthy()
        return health
    finally:
        for key, value in snapshot.items():
            setattr(config, key, value)
        config.secret_key = original_secret
        session.flush()


def object_storage_available_for_acceleration(session: Session) -> bool:
    provider = build_object_storage_provider(session)
    if provider is None:
        return False
    config = get_or_create_object_storage_config(session)
    if not config.health_check_enabled:
        return True
    health = provider.is_healthy()
    config.last_health_ok = health.ok
    config.last_health_error = None if health.ok else health.summary
    config.last_health_checked_at = utcnow()
    session.commit()
    return health.ok


def list_object_storage_sync_records(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
) -> dict[str, object]:
    pattern = (q or "").strip().lower()
    asset_by_id = {asset.id: asset for asset in session.query(Asset).all()}
    records: list[ObjectStorageSyncRecordRead] = []

    for item in repo.list_mirror_queue_items(session):
        records.append(
            _object_storage_sync_record_read(
                item,
                record_type="mirror",
                asset=asset_by_id.get(item.asset_id),
            )
        )

    for item in repo.list_remote_delete_queue_items(session):
        records.append(
            _object_storage_sync_record_read(
                item,
                record_type="remote_delete",
            )
        )

    for item in repo.list_local_delete_queue_items(session):
        records.append(
            _object_storage_sync_record_read(
                item,
                record_type="local_delete",
            )
        )

    for item in repo.list_remote_upload_queue_items(session):
        records.append(
            _object_storage_sync_record_read(
                item,
                record_type="remote_upload",
                asset=asset_by_id.get(item.asset_id),
            )
        )

    if pattern:
        records = [
            record
            for record in records
            if pattern in record.object_key.lower()
            or pattern in (record.asset_file_name or "").lower()
            or pattern in record.status.lower()
            or pattern in record.record_type.lower()
        ]

    records.sort(key=lambda item: (item.updated_at, item.created_at), reverse=True)
    total = len(records)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    items = records[start:end]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


ObjectStorageSyncRecordType = Literal[
    "mirror",
    "local_delete",
    "remote_delete",
    "remote_upload",
]


def _object_storage_sync_record_read(
    item: Any,
    *,
    record_type: ObjectStorageSyncRecordType,
    asset: Asset | None = None,
) -> ObjectStorageSyncRecordRead:
    object_key = item.storage_path if record_type == "local_delete" else item.object_key
    asset_id = item.asset_id if record_type in {"mirror", "remote_upload"} else None
    return ObjectStorageSyncRecordRead(
        id=item.id,
        record_type=record_type,
        status=item.status,
        object_key=object_key,
        asset_id=asset_id,
        asset_file_name=asset.file_name if asset is not None else None,
        asset_resource_key=asset.resource_key if asset is not None else None,
        retry_count=item.retry_count,
        last_error=item.last_error,
        started_at=item.started_at,
        finished_at=item.finished_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def retry_object_storage_sync_record(
    session: Session,
    *,
    record_type: ObjectStorageSyncRecordType,
    record_id: str,
) -> ObjectStorageSyncRecordRead:
    getters = {
        "mirror": repo.get_mirror_queue_item,
        "local_delete": repo.get_local_delete_queue_item,
        "remote_delete": repo.get_remote_delete_queue_item,
        "remote_upload": repo.get_remote_upload_queue_item,
    }
    item = getters[record_type](session, record_id)
    if item is None:
        raise ResourceNotFound("OSS 同步记录不存在")
    if item.status != "failed":
        raise StateConflict("仅失败的 OSS 同步记录可以重试")

    item.status = "retrying"
    item.next_retry_at = utcnow()
    item.last_error = None
    item.started_at = None
    item.finished_at = None
    asset: Asset | None = None
    if record_type in {"mirror", "remote_upload"}:
        asset = repo.find_asset_by_id(session, item.asset_id)
        if asset is not None:
            if record_type == "mirror":
                asset.mirror_status = "retrying"
                asset.mirror_last_error = None
            else:
                asset.remote_status = "retrying"
    session.commit()
    session.refresh(item)
    if asset is not None:
        session.refresh(asset)
    return _object_storage_sync_record_read(
        item,
        record_type=record_type,
        asset=asset,
    )


def should_use_direct_upload(session: Session) -> bool:
    return build_object_storage_provider(session) is not None


def queue_asset_mirror(session: Session, asset: Asset) -> AssetMirrorQueueItem:
    session.flush()
    existing = repo.find_active_mirror_queue_item_for_asset(session, asset.id)
    if existing is not None:
        return existing
    item = repo.create_mirror_queue_item(
        session,
        asset_id=asset.id,
        object_key=object_key_for_asset(asset),
        status="queued",
        retry_count=0,
        next_retry_at=utcnow(),
    )
    asset.mirror_status = "queued"
    asset.mirror_last_error = None
    session.flush()
    return item


def queue_asset_remote_upload(session: Session, asset: Asset) -> tuple[AssetRemoteUploadQueueItem | None, bool]:
    local_path = Path(asset.storage_path)
    if not local_path.exists() or not local_path.is_file():
        return None, False
    existing = repo.find_active_remote_upload_queue_item_for_asset(session, asset.id)
    if existing is not None:
        return existing, False
    object_key = object_key_for_asset(asset)
    if not object_key:
        return None, False
    item = repo.create_remote_upload_queue_item(
        session,
        asset_id=asset.id,
        object_key=object_key,
        status="queued",
        retry_count=0,
        next_retry_at=utcnow(),
    )
    asset.remote_object_key = object_key
    asset.remote_status = "queued"
    session.flush()
    return item, True


def enqueue_missing_remote_assets(session: Session) -> tuple[int, int]:
    scanned = 0
    enqueued = 0
    for asset in repo.list_assets_missing_remote_sync(session):
        local_path = Path(asset.storage_path)
        if not local_path.exists() or not local_path.is_file():
            continue
        scanned += 1
        _queue_item, created = queue_asset_remote_upload(session, asset)
        if created:
            enqueued += 1
    session.flush()
    return scanned, enqueued


def queue_remote_asset_delete(
    session: Session,
    *,
    object_key: str,
    error: str | None = None,
) -> AssetRemoteDeleteQueueItem:
    normalized_key = object_key.strip()
    existing = repo.find_active_remote_delete_queue_item(session, normalized_key)
    if existing is not None:
        if error:
            existing.last_error = error
        session.flush()
        return existing
    item = repo.create_remote_delete_queue_item(
        session,
        object_key=normalized_key,
        status="queued",
        retry_count=0,
        next_retry_at=utcnow(),
        last_error=error,
    )
    session.flush()
    return item


def queue_local_asset_delete(session: Session, *, storage_path: Path) -> str:
    target = assert_managed_local_path(storage_path)
    normalized_path = str(target)
    existing = repo.find_active_local_delete_queue_item(session, normalized_path)
    if existing is not None:
        return existing.id
    item = repo.create_local_delete_queue_item(
        session,
        storage_path=normalized_path,
        status="queued",
        retry_count=0,
        next_retry_at=utcnow(),
        last_error=None,
    )
    session.flush()
    return item.id


def record_completed_remote_asset_delete(
    session: Session,
    *,
    object_key: str,
) -> AssetRemoteDeleteQueueItem:
    now = utcnow()
    item = repo.create_remote_delete_queue_item(
        session,
        object_key=object_key.strip(),
        status="completed",
        retry_count=0,
        next_retry_at=now,
        started_at=now,
        finished_at=now,
        last_error=None,
    )
    session.flush()
    return item


def dispatch_due_asset_mirror_jobs() -> None:
    session_factory = get_session_factory()
    now = utcnow()
    with session_factory() as session:
        if repo.find_running_mirror_queue_item(session) is not None:
            return
        queue_item = repo.find_due_mirror_queue_item(session, now=now)
        if queue_item is None:
            return
        queue_item.status = "running"
        queue_item.started_at = now
        queue_item.last_error = None
        asset = repo.find_asset_by_id(session, queue_item.asset_id)
        if asset is not None:
            asset.mirror_status = "running"
            asset.mirror_last_error = None
        session.commit()
        queue_item_id = queue_item.id

    try:
        _execute_asset_mirror(queue_item_id=queue_item_id)
    except Exception as exc:  # pragma: no cover - failure path exercised via tests
        logger.exception("Asset mirror job failed")
        _mark_asset_mirror_failed(
            queue_item_id=queue_item_id,
            error=str(exc),
            integrity_failure=isinstance(exc, AssetMirrorIntegrityError),
        )


@data_storage_locked
def dispatch_due_remote_asset_delete_jobs() -> None:
    if data_storage_cleanup_pending():
        return
    session_factory = get_session_factory()
    now = utcnow()
    with session_factory() as session:
        if repo.find_running_remote_delete_queue_item(session) is not None:
            return
        queue_item = repo.find_due_remote_delete_queue_item(session, now=now)
        if queue_item is None:
            return
        queue_item.status = "running"
        queue_item.started_at = now
        queue_item.last_error = None
        session.commit()
        queue_item_id = queue_item.id

    try:
        _execute_remote_asset_delete(queue_item_id=queue_item_id)
    except Exception as exc:  # pragma: no cover - failure path exercised via tests
        logger.exception("Remote asset delete job failed")
        _mark_remote_asset_delete_failed(queue_item_id=queue_item_id, error=str(exc))


@data_storage_locked
def dispatch_due_local_asset_delete_jobs() -> None:
    if data_storage_cleanup_pending():
        return
    session_factory = get_session_factory()
    now = utcnow()
    with session_factory() as session:
        if repo.find_running_local_delete_queue_item(session) is not None:
            return
        queue_item = repo.find_due_local_delete_queue_item(session, now=now)
        if queue_item is None:
            return
        queue_item.status = "running"
        queue_item.started_at = now
        queue_item.last_error = None
        session.commit()
        queue_item_id = queue_item.id

    process_local_asset_delete(queue_item_id)


@data_storage_locked
def process_local_asset_delete(queue_item_id: str) -> None:
    try:
        _execute_local_asset_delete(queue_item_id=queue_item_id)
    except Exception as exc:
        logger.exception("Local asset delete job failed")
        _mark_local_asset_delete_failed(queue_item_id=queue_item_id, error=str(exc))


@data_storage_locked
def process_remote_asset_delete(queue_item_id: str, *, provider: Any | None = None) -> None:
    try:
        _execute_remote_asset_delete(queue_item_id=queue_item_id, provider_override=provider)
    except Exception as exc:
        logger.exception("Remote asset delete job failed")
        _mark_remote_asset_delete_failed(queue_item_id=queue_item_id, error=str(exc))


def dispatch_due_remote_asset_upload_jobs() -> None:
    session_factory = get_session_factory()
    now = utcnow()
    with session_factory() as session:
        if repo.find_running_remote_upload_queue_item(session) is not None:
            return
        queue_item = repo.find_due_remote_upload_queue_item(session, now=now)
        if queue_item is None:
            return
        queue_item.status = "running"
        queue_item.started_at = now
        queue_item.last_error = None
        asset = repo.find_asset_by_id(session, queue_item.asset_id)
        if asset is not None:
            asset.remote_status = "running"
        session.commit()
        queue_item_id = queue_item.id

    try:
        _execute_remote_asset_upload(queue_item_id=queue_item_id)
    except Exception as exc:  # pragma: no cover - failure path exercised via tests
        logger.exception("Remote asset upload job failed")
        _mark_remote_asset_upload_failed(queue_item_id=queue_item_id, error=str(exc))


def reconcile_object_storage_remote_sync() -> int:
    session_factory = get_session_factory()
    with session_factory() as session:
        config = get_or_create_object_storage_config(session)
        if not config.enabled:
            return 0
        provider = build_object_storage_maintenance_provider(session)
        if provider is None:
            return 0
        _scanned, enqueued = enqueue_missing_remote_assets(session)
        session.commit()
        return enqueued


def _execute_asset_mirror(*, queue_item_id: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_mirror_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Mirror queue item not found")
        asset = repo.find_asset_by_id(session, queue_item.asset_id)
        if asset is None:
            queue_item.status = "completed"
            queue_item.finished_at = utcnow()
            session.commit()
            return
        provider = build_object_storage_maintenance_provider(session)
        if provider is None:
            raise ValidationError("OSS 当前不可用，无法执行本地镜像")
        config = get_or_create_object_storage_config(session)
        target_path = assert_managed_local_path(Path(asset.storage_path))
        expected_path = build_local_path(identity_from_resource_key(asset.resource_key), asset.scope)
        if target_path != expected_path:
            raise ValidationError("资源本地镜像路径与范围不一致")
        expected_size = asset.byte_size
        expected_sha256 = str(asset.sha256 or "").strip().lower()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(f".{target_path.name}.{queue_item_id}.mirror.tmp")
    try:
        byte_size, etag = provider.download_to_local(
            object_key=queue_item.object_key,
            dest_path=temporary_path,
            bandwidth_limit_bps=int(config.mirror_bandwidth_limit_bps or 0),
        )
        actual_size = temporary_path.stat().st_size
        if byte_size != actual_size:
            raise ValidationError("OSS 镜像下载返回的大小与实际文件不一致")
        if expected_size is not None and actual_size != expected_size:
            raise AssetMirrorIntegrityError("OSS 镜像文件大小与资源记录不一致")
        actual_sha256 = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise AssetMirrorIntegrityError("OSS 镜像文件摘要与资源记录不一致")
        with temporary_path.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary_path.replace(target_path)
        descriptor = os.open(target_path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary_path.unlink(missing_ok=True)

    with session_factory() as session:
        queue_item = repo.get_mirror_queue_item(session, queue_item_id)
        asset = repo.find_asset_by_id(session, queue_item.asset_id if queue_item is not None else "")
        now = utcnow()
        if queue_item is not None:
            queue_item.status = "completed"
            queue_item.finished_at = now
            queue_item.last_error = None
        if asset is not None:
            asset.byte_size = asset.byte_size or byte_size
            asset.remote_etag = asset.remote_etag or etag
            asset.remote_status = "available"
            asset.mirror_status = "completed"
            asset.mirror_last_error = None
            if not asset.sha256:
                asset.sha256 = actual_sha256
        session.commit()


def _mark_asset_mirror_failed(*, queue_item_id: str, error: str, integrity_failure: bool = False) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_mirror_queue_item(session, queue_item_id)
        if queue_item is None:
            return
        asset = repo.find_asset_by_id(session, queue_item.asset_id)
        config = get_or_create_object_storage_config(session)
        queue_item.retry_count += 1
        queue_item.last_error = error
        queue_item.finished_at = utcnow()
        if queue_item.retry_count > int(config.mirror_retry_count):
            queue_item.status = "failed"
        else:
            queue_item.status = "retrying"
            queue_item.next_retry_at = utcnow() + timedelta(seconds=30 * queue_item.retry_count)
        if asset is not None:
            if integrity_failure:
                asset.remote_status = "invalid"
            asset.mirror_status = "failed" if queue_item.status == "failed" else "retrying"
            asset.mirror_last_error = error
        session.commit()


def _execute_remote_asset_upload(*, queue_item_id: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_remote_upload_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Remote upload queue item not found")
        asset = repo.find_asset_by_id(session, queue_item.asset_id)
        if asset is None:
            raise ResourceNotFound("Asset not found")
        local_path = Path(asset.storage_path)
        if not local_path.exists() or not local_path.is_file():
            raise ResourceNotFound("Local asset file not found")
        provider = build_object_storage_maintenance_provider(session)
        if provider is None:
            raise ValidationError("OSS 当前不可用，无法执行远端同步")
        object_key = object_key_for_asset(asset)
        mime_type = asset.mime_type
        content = local_path.read_bytes()

    try:
        head = provider.upload_bytes(
            object_key=object_key,
            data=content,
            content_type=mime_type,
        )
        if head.content_length is not None and head.content_length != len(content):
            raise ValidationError("OSS 补同步后的对象大小与本地文件不一致")
    except Exception:
        try:
            provider.delete_object(object_key=object_key)
        except Exception:
            logger.exception("Failed to clean remote object after sync failure: %s", object_key)
        raise

    with session_factory() as session:
        queue_item = repo.get_remote_upload_queue_item(session, queue_item_id)
        asset = repo.find_asset_by_id(session, queue_item.asset_id if queue_item is not None else "")
        now = utcnow()
        if queue_item is not None:
            queue_item.status = "completed"
            queue_item.finished_at = now
            queue_item.last_error = None
        if asset is not None:
            asset.storage_provider = "bitiful"
            asset.remote_object_key = object_key
            asset.remote_status = "available"
            asset.remote_uploaded_at = now
            asset.remote_etag = head.etag
            asset.byte_size = asset.byte_size or head.content_length or len(content)
            asset.mime_type = asset.mime_type or head.content_type or mime_type
            asset.oss_acceleration_enabled_at_upload = True
        session.commit()


def _mark_remote_asset_upload_failed(*, queue_item_id: str, error: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_remote_upload_queue_item(session, queue_item_id)
        if queue_item is None:
            return
        asset = repo.find_asset_by_id(session, queue_item.asset_id)
        config = get_or_create_object_storage_config(session)
        queue_item.retry_count += 1
        queue_item.last_error = error
        queue_item.finished_at = utcnow()
        if queue_item.retry_count > int(config.mirror_retry_count):
            queue_item.status = "failed"
        else:
            queue_item.status = "retrying"
            queue_item.next_retry_at = utcnow() + timedelta(seconds=30 * queue_item.retry_count)
        if asset is not None:
            asset.remote_status = "failed" if queue_item.status == "failed" else "retrying"
        session.commit()


def _execute_remote_asset_delete(*, queue_item_id: str, provider_override: Any | None = None) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_remote_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Remote delete queue item not found")
        provider = provider_override or build_object_storage_maintenance_provider(session)
        if provider is None:
            raise ValidationError("OSS 当前不可用，无法执行远端删除补偿")
        object_key = queue_item.object_key

    provider.delete_object(object_key=object_key)

    with session_factory() as session:
        queue_item = repo.get_remote_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            return
        now = utcnow()
        queue_item.status = "completed"
        queue_item.finished_at = now
        queue_item.next_retry_at = now
        queue_item.last_error = None
        session.commit()


def _execute_local_asset_delete(*, queue_item_id: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_local_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Local delete queue item not found")
        raw_path = Path(queue_item.storage_path)
        if raw_path.is_symlink():
            raise ValidationError("拒绝删除符号链接资源")
        target = assert_managed_local_path(raw_path)

    target.unlink(missing_ok=True)
    with suppress(OSError):
        target.parent.rmdir()

    with session_factory() as session:
        queue_item = repo.get_local_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            return
        now = utcnow()
        queue_item.status = "completed"
        queue_item.finished_at = now
        queue_item.next_retry_at = now
        queue_item.last_error = None
        session.commit()


def _mark_local_asset_delete_failed(*, queue_item_id: str, error: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_local_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            return
        config = get_or_create_object_storage_config(session)
        queue_item.retry_count += 1
        queue_item.last_error = error
        queue_item.finished_at = utcnow()
        if queue_item.retry_count > int(config.mirror_retry_count):
            queue_item.status = "failed"
        else:
            queue_item.status = "retrying"
            queue_item.next_retry_at = utcnow() + timedelta(seconds=30 * queue_item.retry_count)
        session.commit()


def _mark_remote_asset_delete_failed(*, queue_item_id: str, error: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_remote_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            return
        config = get_or_create_object_storage_config(session)
        queue_item.retry_count += 1
        queue_item.last_error = error
        queue_item.finished_at = utcnow()
        if queue_item.retry_count > int(config.mirror_retry_count):
            queue_item.status = "failed"
        else:
            queue_item.status = "retrying"
            queue_item.next_retry_at = utcnow() + timedelta(seconds=30 * queue_item.retry_count)
        session.commit()


def sign_asset_download_url(session: Session, asset: Asset) -> str | None:
    if asset.remote_status != "available":
        return None
    provider = build_object_storage_provider(session)
    if provider is None:
        return None
    config = get_or_create_object_storage_config(session)
    object_key = object_key_for_asset(asset)
    if not object_key:
        return None
    if config.health_check_enabled:
        try:
            provider.head_object(object_key=object_key)
        except Exception:
            return None
    expires_in = int(config.public_download_expire_seconds or 600)
    token_base_url = str(config.public_base_url or "").strip().rstrip("/")
    token_key = str(config.cdn_token_key or "").strip()
    if token_base_url and token_key:
        quoted_path = quote(f"/{object_key.lstrip('/')}", safe="/-._~")
        deadline = int(time.time()) + max(expires_in, 30)
        token = hashlib.md5(f"{token_key}{quoted_path}{deadline}".encode()).hexdigest()
        return f"{token_base_url}{quoted_path}?_btf_tk={token}&_ts={deadline}"
    try:
        return provider.sign_download(
            object_key=object_key,
            expires_in=expires_in,
        )
    except Exception:
        logger.exception("Failed to sign asset download url")
        return None


def upload_asset_bytes_to_remote(
    session: Session,
    *,
    asset: Asset,
    content: bytes,
    mime_type: str | None,
) -> Asset:
    provider = build_object_storage_provider(session)
    if provider is None:
        raise ValidationError("OSS 不可用，无法执行远端上传")
    object_key = object_key_for_asset(asset)
    try:
        head = provider.upload_bytes(
            object_key=object_key,
            data=content,
            content_type=mime_type,
        )
        if head.content_length is not None and head.content_length != len(content):
            raise ValidationError("OSS 上传后的对象大小与源文件不一致")
    except Exception:
        try:
            provider.delete_object(object_key=object_key)
        except Exception as cleanup_exc:
            logger.exception("Failed to clean remote object after upload failure: %s", object_key)
            try:
                with get_session_factory()() as cleanup_session:
                    queue_remote_asset_delete(
                        cleanup_session,
                        object_key=object_key,
                        error=f"上传失败后的目标清理待重试：{cleanup_exc}",
                    )
                    cleanup_session.commit()
            except Exception:
                logger.exception("Failed to persist remote cleanup retry: %s", object_key)
        raise
    asset.storage_provider = "bitiful"
    asset.remote_status = "available"
    asset.remote_uploaded_at = utcnow()
    asset.remote_etag = head.etag
    asset.byte_size = asset.byte_size or head.content_length or len(content)
    asset.mime_type = asset.mime_type or head.content_type or mime_type
    return asset


def asset_admin_read_from_model(asset: Asset) -> AssetAdminRead:
    site_url = (get_settings().site_url or "").rstrip("/")
    resource_key = str(asset.resource_key or "").strip().lstrip("/")
    internal_url = f"/media/{resource_key}"
    public_path = f"/media/{asset.public_slug}" if asset.public_slug else internal_url
    public_url = f"{site_url}{public_path}" if site_url else public_path
    if asset.visibility != "public":
        public_url = None
    return AssetAdminRead(
        id=asset.id,
        file_name=asset.file_name,
        resource_key=asset.resource_key,
        public_slug=asset.public_slug,
        visibility=asset.visibility,
        scope=asset.scope,
        category=asset.category,
        note=asset.note,
        storage_path=asset.storage_path,
        internal_url=internal_url,
        public_url=public_url,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        storage_provider=asset.storage_provider,
        remote_status=asset.remote_status,
        mirror_status=asset.mirror_status,
        mirror_last_error=asset.mirror_last_error,
        oss_acceleration_enabled_at_upload=bool(asset.oss_acceleration_enabled_at_upload),
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )

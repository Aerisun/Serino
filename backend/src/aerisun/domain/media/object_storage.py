from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from aerisun.core.base import utcnow, uuid_str
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.core.time import normalize_shanghai_datetime
from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.media import repository as repo
from aerisun.domain.media.models import (
    Asset,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
    ObjectStorageConfig,
)
from aerisun.domain.media.schemas import (
    AssetAdminRead,
    AssetUploadPlanWrite,
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


@dataclass(slots=True)
class ObjectHead:
    content_length: int | None
    content_type: str | None
    etag: str | None
    last_modified: datetime | None


class BitifulObjectStorageProvider:
    def __init__(self, config: ObjectStorageConfig) -> None:
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

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=str(config.region or "").strip() or None,
            aws_access_key_id=str(config.access_key or "").strip(),
            aws_secret_access_key=str(config.secret_key or "").strip(),
            config=BotoConfig(signature_version="s3v4"),
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


def restore_object_storage_config(session: Session, snapshot: dict[str, Any]) -> None:
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


def update_object_storage_config(session: Session, payload: ObjectStorageConfigUpdate) -> ObjectStorageConfigRead:
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
        asset = asset_by_id.get(item.asset_id)
        record = ObjectStorageSyncRecordRead(
            id=item.id,
            record_type="mirror",
            status=item.status,
            object_key=item.object_key,
            asset_id=item.asset_id,
            asset_file_name=asset.file_name if asset is not None else None,
            asset_resource_key=asset.resource_key if asset is not None else None,
            retry_count=item.retry_count,
            last_error=item.last_error,
            started_at=item.started_at,
            finished_at=item.finished_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        records.append(record)

    for item in repo.list_remote_delete_queue_items(session):
        records.append(
            ObjectStorageSyncRecordRead(
                id=item.id,
                record_type="remote_delete",
                status=item.status,
                object_key=item.object_key,
                retry_count=item.retry_count,
                last_error=item.last_error,
                started_at=item.started_at,
                finished_at=item.finished_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    for item in repo.list_remote_upload_queue_items(session):
        asset = asset_by_id.get(item.asset_id)
        records.append(
            ObjectStorageSyncRecordRead(
                id=item.id,
                record_type="remote_upload",
                status=item.status,
                object_key=item.object_key,
                asset_id=item.asset_id,
                asset_file_name=asset.file_name if asset is not None else None,
                asset_resource_key=asset.resource_key if asset is not None else None,
                retry_count=item.retry_count,
                last_error=item.last_error,
                started_at=item.started_at,
                finished_at=item.finished_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
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
        object_key=asset.remote_object_key or asset.resource_key,
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
    object_key = str(asset.remote_object_key or asset.resource_key).strip()
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
        _mark_asset_mirror_failed(queue_item_id=queue_item_id, error=str(exc))


def dispatch_due_remote_asset_delete_jobs() -> None:
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
        target_path = Path(asset.storage_path)

    byte_size, etag = provider.download_to_local(
        object_key=queue_item.object_key,
        dest_path=target_path,
        bandwidth_limit_bps=int(config.mirror_bandwidth_limit_bps or 0),
    )

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
            asset.mirror_status = "completed"
            asset.mirror_last_error = None
            if not asset.sha256 and Path(asset.storage_path).exists():
                asset.sha256 = hashlib.sha256(Path(asset.storage_path).read_bytes()).hexdigest()
        session.commit()


def _mark_asset_mirror_failed(*, queue_item_id: str, error: str) -> None:
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
        object_key = str(asset.remote_object_key or asset.resource_key).strip()
        mime_type = asset.mime_type
        content = local_path.read_bytes()

    head = provider.upload_bytes(
        object_key=object_key,
        data=content,
        content_type=mime_type,
    )

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


def _execute_remote_asset_delete(*, queue_item_id: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        queue_item = repo.get_remote_delete_queue_item(session, queue_item_id)
        if queue_item is None:
            raise ResourceNotFound("Remote delete queue item not found")
        provider = build_object_storage_maintenance_provider(session)
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
    provider = build_object_storage_provider(session)
    if provider is None:
        return None
    config = get_or_create_object_storage_config(session)
    object_key = str(asset.remote_object_key or asset.resource_key).strip()
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
    head = provider.upload_bytes(
        object_key=str(asset.remote_object_key or asset.resource_key).strip(),
        data=content,
        content_type=mime_type,
    )
    asset.storage_provider = "bitiful"
    asset.remote_status = "available"
    asset.remote_uploaded_at = utcnow()
    asset.remote_etag = head.etag
    asset.byte_size = asset.byte_size or head.content_length or len(content)
    asset.mime_type = asset.mime_type or head.content_type or mime_type
    return asset


def build_asset_storage_path(resource_key: str) -> Path:
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir / resource_key


def guess_extension(file_name: str, mime_type: str | None) -> str:
    suffix = Path(file_name).suffix.lower().lstrip(".")
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed:
        return guessed.lstrip(".").lower()
    return "bin"


def build_resource_key_from_digest(
    *,
    file_name: str,
    digest: str,
    mime_type: str | None,
    category: str,
    visibility: str,
    digest_prefix_length: int = 12,
) -> str:
    ext = guess_extension(file_name, mime_type)
    key = re.sub(r"[^a-z0-9_-]+", "", str(digest or "").strip().lower())
    if not key:
        key = uuid_str().replace("-", "")
    prefix_length = max(12, min(int(digest_prefix_length), len(key)))
    return f"{visibility}/assets/{category}/{key[:prefix_length]}.{ext}"


def build_resource_key_for_plan(plan: AssetUploadPlanWrite, *, category: str, visibility: str) -> str:
    digest = str(plan.sha256 or "").strip().lower()
    if not digest:
        digest = uuid_str().replace("-", "")
    return build_resource_key_from_digest(
        file_name=plan.file_name,
        digest=digest,
        mime_type=plan.mime_type,
        category=category,
        visibility=visibility,
    )


def asset_admin_read_from_model(asset: Asset) -> AssetAdminRead:
    site_url = (get_settings().site_url or "").rstrip("/")
    internal_url = f"/media/{asset.resource_key}"
    public_url = f"{site_url}{internal_url}" if site_url else internal_url
    if asset.visibility != "public":
        public_url = None
    return AssetAdminRead(
        id=asset.id,
        file_name=asset.file_name,
        resource_key=asset.resource_key,
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

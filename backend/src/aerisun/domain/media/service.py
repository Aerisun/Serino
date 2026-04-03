from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from aerisun.domain.exceptions import PayloadTooLarge, ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.exceptions import ValidationError as DomainValidationError
from aerisun.domain.media import repository as repo
from aerisun.domain.media.models import Asset
from aerisun.domain.media.object_storage import (
    asset_admin_read_from_model,
    build_asset_storage_path,
    build_object_storage_maintenance_provider,
    build_object_storage_provider,
    build_resource_key_for_plan,
    build_resource_key_from_digest,
    get_or_create_object_storage_config,
    queue_asset_mirror,
    record_completed_remote_asset_delete,
    queue_remote_asset_delete,
    should_use_direct_upload,
    sign_asset_download_url,
    upload_asset_bytes_to_remote,
)
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.media.schemas import (
    AssetAdminRead,
    AssetAdminUpdate,
    AssetUploadCompleteWrite,
    AssetUploadPlanRead,
    AssetUploadPlanWrite,
)

logger = logging.getLogger(__name__)
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


def _normalize_visibility(value: str | None) -> str:
    normalized = (value or "internal").strip().lower()
    if normalized not in {"internal", "public"}:
        raise DomainValidationError("资源可见性仅支持 internal 或 public")
    return normalized


def _normalize_category(value: str | None) -> str:
    category = (value or "general").strip().lower()
    category = _SAFE_SLUG_RE.sub("-", category).strip("-")
    return category or "general"


def _normalize_scope(value: str | None) -> str:
    normalized = (value or "user").strip().lower()
    if normalized not in {"system", "user"}:
        raise DomainValidationError("资源范围仅支持 system 或 user")
    return normalized


def _normalize_note(value: str | None) -> str | None:
    note = (value or "").strip()
    return note or None


def list_assets(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    scope: str | None = None,
) -> dict:
    items, total = repo.find_assets_paginated(session, page=page, page_size=page_size, q=q, scope=scope)
    return {
        "items": [asset_admin_read_from_model(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _build_resource_key(
    *,
    file_name: str,
    content: bytes,
    mime_type: str | None,
    category: str,
    visibility: str,
) -> tuple[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    resource_key = build_resource_key_from_digest(
        file_name=file_name,
        digest=digest,
        mime_type=mime_type,
        category=category,
        visibility=visibility,
    )
    return resource_key, digest


def _existing_asset_or_none(session: Session, resource_key: str) -> Asset | None:
    asset = repo.find_asset_by_resource_key(session, resource_key)
    if asset is None:
        return None
    return asset


def _write_local_file(storage_path: Path, content: bytes) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if storage_path.exists():
        return
    storage_path.write_bytes(content)


def _create_asset_record(
    session: Session,
    *,
    file_name: str,
    resource_key: str,
    visibility: str,
    scope: str,
    category: str,
    note: str | None,
    storage_path: Path,
    mime_type: str | None,
    byte_size: int | None,
    sha256: str | None,
    storage_provider: str = "local",
    remote_object_key: str | None = None,
    remote_status: str = "none",
    mirror_status: str = "completed",
    oss_acceleration_enabled_at_upload: bool = False,
) -> Asset:
    return repo.create_asset(
        session,
        file_name=file_name,
        resource_key=resource_key,
        visibility=visibility,
        scope=scope,
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=byte_size,
        sha256=sha256,
        storage_provider=storage_provider,
        remote_object_key=remote_object_key,
        remote_status=remote_status,
        mirror_status=mirror_status,
        mirror_last_error=None,
        oss_acceleration_enabled_at_upload=oss_acceleration_enabled_at_upload,
    )


def upload_asset(
    session: Session,
    file_name: str,
    content: bytes,
    mime_type: str | None,
    *,
    visibility: str = "internal",
    scope: str = "user",
    category: str = "general",
    note: str | None = None,
) -> AssetAdminRead:
    from aerisun.domain.automation.events import emit_asset_uploaded

    normalized_visibility = _normalize_visibility(visibility)
    normalized_scope = _normalize_scope(scope)
    normalized_category = _normalize_category(category)
    normalized_note = _normalize_note(note)
    resource_key, sha = _build_resource_key(
        file_name=file_name,
        content=content,
        mime_type=mime_type,
        category=normalized_category,
        visibility=normalized_visibility,
    )
    existing = _existing_asset_or_none(session, resource_key)
    if existing is not None:
        storage_path = Path(existing.storage_path)
        if not storage_path.exists():
            provider = build_object_storage_provider(session)
            if provider is not None and existing.storage_provider == "bitiful" and existing.remote_status == "available":
                queue_asset_mirror(session, existing)
                session.commit()
                session.refresh(existing)
            else:
                _write_local_file(storage_path, content)
        return asset_admin_read_from_model(existing)

    storage_path = build_asset_storage_path(resource_key)
    use_oss = build_object_storage_provider(session) is not None
    if use_oss:
        asset = _create_asset_record(
            session,
            file_name=file_name,
            resource_key=resource_key,
            visibility=normalized_visibility,
            scope=normalized_scope,
            category=normalized_category,
            note=normalized_note,
            storage_path=storage_path,
            mime_type=mime_type,
            byte_size=len(content),
            sha256=sha,
            storage_provider="bitiful",
            remote_object_key=resource_key,
            remote_status="available",
            mirror_status="queued",
            oss_acceleration_enabled_at_upload=True,
        )
        upload_asset_bytes_to_remote(session, asset=asset, content=content, mime_type=mime_type)
        queue_asset_mirror(session, asset)
    else:
        _write_local_file(storage_path, content)
        asset = _create_asset_record(
            session,
            file_name=file_name,
            resource_key=resource_key,
            visibility=normalized_visibility,
            scope=normalized_scope,
            category=normalized_category,
            note=normalized_note,
            storage_path=storage_path,
            mime_type=mime_type,
            byte_size=len(content),
            sha256=sha,
        )
    session.commit()
    session.refresh(asset)
    emit_asset_uploaded(
        session,
        asset_id=asset.id,
        resource_key=asset.resource_key,
        visibility=asset.visibility,
        scope=asset.scope,
        category=asset.category,
        file_name=asset.file_name,
    )
    return asset_admin_read_from_model(asset)


def prepare_asset_upload(session: Session, payload: AssetUploadPlanWrite) -> AssetUploadPlanRead:
    normalized_visibility = _normalize_visibility(payload.visibility)
    normalized_scope = _normalize_scope(payload.scope)
    normalized_category = _normalize_category(payload.category)
    normalized_note = _normalize_note(payload.note)
    resource_key = build_resource_key_for_plan(
        payload,
        category=normalized_category,
        visibility=normalized_visibility,
    )
    existing = _existing_asset_or_none(session, resource_key)
    if existing is not None:
        return AssetUploadPlanRead(mode="existing", asset=asset_admin_read_from_model(existing))

    provider = build_object_storage_provider(session)
    if provider is None or not should_use_direct_upload(session):
        return AssetUploadPlanRead(mode="local")

    storage_path = build_asset_storage_path(resource_key)
    asset = _create_asset_record(
        session,
        file_name=payload.file_name,
        resource_key=resource_key,
        visibility=normalized_visibility,
        scope=normalized_scope,
        category=normalized_category,
        note=normalized_note,
        storage_path=storage_path,
        mime_type=payload.mime_type,
        byte_size=payload.byte_size,
        sha256=payload.sha256.lower(),
        storage_provider="bitiful",
        remote_object_key=resource_key,
        remote_status="pending_upload",
        mirror_status="queued",
        oss_acceleration_enabled_at_upload=True,
    )
    config = get_or_create_object_storage_config(session)
    upload_url = provider.sign_upload(
        object_key=resource_key,
        content_type=payload.mime_type,
        expires_in=int(config.upload_expire_seconds or 300),
    )
    session.commit()
    session.refresh(asset)
    return AssetUploadPlanRead(
        mode="oss",
        asset_id=asset.id,
        resource_key=asset.resource_key,
        upload_url=upload_url,
        upload_method="PUT",
        upload_headers={},
        expires_at=datetime.now(tz=UTC) + timedelta(seconds=int(config.upload_expire_seconds or 300)),
    )


def complete_asset_upload(session: Session, payload: AssetUploadCompleteWrite) -> AssetAdminRead:
    from aerisun.domain.automation.events import emit_asset_uploaded

    asset = repo.find_asset_by_id(session, payload.asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")
    if asset.remote_status not in {"pending_upload", "uploading", "none"}:
        if asset.remote_status == "available":
            return asset_admin_read_from_model(asset)
        raise StateConflict("当前资源上传状态不可完成")

    provider = build_object_storage_provider(session)
    if provider is None:
        raise ValidationError("OSS 当前不可用，无法完成直传资源")

    head = provider.head_object(object_key=str(asset.remote_object_key or asset.resource_key))
    asset.storage_provider = "bitiful"
    asset.remote_status = "available"
    asset.remote_uploaded_at = datetime.now(tz=UTC)
    asset.remote_etag = head.etag
    asset.byte_size = asset.byte_size or head.content_length
    asset.mime_type = asset.mime_type or head.content_type
    queue_asset_mirror(session, asset)
    session.commit()
    session.refresh(asset)
    emit_asset_uploaded(
        session,
        asset_id=asset.id,
        resource_key=asset.resource_key,
        visibility=asset.visibility,
        scope=asset.scope,
        category=asset.category,
        file_name=asset.file_name,
    )
    return asset_admin_read_from_model(asset)


def get_asset(session: Session, asset_id: str) -> AssetAdminRead:
    obj = repo.find_asset_by_id(session, asset_id)
    if obj is None:
        raise ResourceNotFound("Asset not found")
    return asset_admin_read_from_model(obj)


def update_asset(session: Session, asset_id: str, payload: AssetAdminUpdate) -> AssetAdminRead:
    from aerisun.domain.automation.events import emit_asset_updated

    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")

    next_visibility = _normalize_visibility(payload.visibility or asset.visibility)
    next_scope = _normalize_scope(payload.scope or asset.scope)
    next_category = _normalize_category(payload.category or asset.category)
    next_note = _normalize_note(payload.note if payload.note is not None else asset.note)

    digest = asset.sha256
    current_path = Path(asset.storage_path)
    if not digest and current_path.exists():
        digest = hashlib.sha256(current_path.read_bytes()).hexdigest()

    if digest:
        next_resource_key = build_resource_key_from_digest(
            file_name=asset.file_name,
            digest=digest,
            mime_type=asset.mime_type,
            category=next_category,
            visibility=next_visibility,
        )
    else:
        next_resource_key = asset.resource_key

    if next_resource_key != asset.resource_key:
        existing = repo.find_asset_by_resource_key(session, next_resource_key)
        if existing is not None and existing.id != asset.id:
            raise DomainValidationError("目标资源标识已存在")

        previous_remote_object_key = asset.remote_object_key
        next_storage_path = build_asset_storage_path(next_resource_key)
        if current_path.exists() and next_storage_path != current_path:
            next_storage_path.parent.mkdir(parents=True, exist_ok=True)
            current_path.replace(next_storage_path)
            asset.storage_path = str(next_storage_path)
        else:
            asset.storage_path = str(next_storage_path)

        asset.resource_key = next_resource_key
        if previous_remote_object_key:
            provider = build_object_storage_maintenance_provider(session)
            if provider is not None and next_storage_path.exists():
                try:
                    provider.upload_bytes(
                        object_key=next_resource_key,
                        data=next_storage_path.read_bytes(),
                        content_type=asset.mime_type,
                    )
                    if previous_remote_object_key != next_resource_key:
                        try:
                            provider.delete_object(object_key=previous_remote_object_key)
                        except Exception as exc:
                            queue_remote_asset_delete(
                                session,
                                object_key=previous_remote_object_key,
                                error=f"远端旧对象删除失败：{exc}",
                            )
                    asset.remote_object_key = next_resource_key
                    asset.remote_status = "available"
                    asset.remote_uploaded_at = datetime.now(tz=UTC)
                except Exception:
                    logger.exception("Failed to move remote asset object; keeping previous remote key")

    asset.visibility = next_visibility
    asset.scope = next_scope
    asset.category = next_category
    asset.note = next_note
    session.commit()
    session.refresh(asset)
    emit_asset_updated(
        session,
        asset_id=asset.id,
        resource_key=asset.resource_key,
        visibility=asset.visibility,
        scope=asset.scope,
        category=asset.category,
    )
    return asset_admin_read_from_model(asset)


def delete_asset(session: Session, asset_id: str) -> None:
    from aerisun.domain.automation.events import emit_asset_deleted

    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")
    _delete_asset_record(session, asset)
    session.commit()
    emit_asset_deleted(
        session,
        asset_id=asset.id,
        resource_key=asset.resource_key,
        file_name=asset.file_name,
    )


def _delete_asset_record(session: Session, asset: Asset) -> None:
    snapshot = {
        "asset_id": asset.id,
        "resource_key": asset.resource_key,
        "file_name": asset.file_name,
    }
    path = Path(asset.storage_path)
    if path.exists():
        path.unlink()
    remote_object_key = str(asset.remote_object_key or "").strip()
    if remote_object_key:
        provider = build_object_storage_maintenance_provider(session)
        if provider is not None:
            try:
                provider.delete_object(object_key=remote_object_key)
                record_completed_remote_asset_delete(
                    session,
                    object_key=remote_object_key,
                )
            except Exception as exc:
                logger.exception("Failed to delete remote asset object %s", remote_object_key)
                queue_remote_asset_delete(
                    session,
                    object_key=remote_object_key,
                    error=f"远端对象删除失败：{exc}",
                )
        else:
            queue_remote_asset_delete(
                session,
                object_key=remote_object_key,
                error="远端对象删除已转入补偿队列：当前 OSS 不可用",
            )
    repo.delete_asset(session, asset)
    return snapshot


def bulk_delete_assets(session: Session, ids: list[str]) -> int:
    from aerisun.domain.automation.events import emit_asset_bulk_deleted

    assets = [asset for asset_id in ids if (asset := repo.find_asset_by_id(session, asset_id)) is not None]
    for asset in assets:
        _delete_asset_record(session, asset)
    affected = len(assets)
    session.commit()
    emit_asset_bulk_deleted(session, ids=ids, affected=affected)
    return affected


def save_comment_image(session: Session, content: bytes, filename: str, mime_type: str | None) -> str:
    from aerisun.domain.automation.events import emit_comment_image_saved

    if mime_type not in _ALLOWED_IMAGE_TYPES:
        raise DomainValidationError("不支持的图片格式")
    community_config = site_config_repo.find_community_config(session)
    configured_limit = int(community_config.image_max_bytes or 0) if community_config is not None else 0
    effective_limit = configured_limit if configured_limit > 0 else _MAX_UPLOAD_BYTES
    if len(content) > effective_limit:
        raise PayloadTooLarge("图片过大，请压缩后重试")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise PayloadTooLarge("图片过大，请压缩后重试")

    asset = upload_asset(
        session,
        filename or "img",
        content,
        mime_type,
        visibility="internal",
        scope="user",
        category="comment",
    )
    emit_comment_image_saved(
        session,
        asset_id=asset.id,
        resource_key=asset.resource_key,
        file_name=asset.file_name,
    )
    return asset.internal_url


def resolve_media_redirect(session: Session, resource_key: str) -> str | None:
    asset = repo.find_asset_by_resource_key(session, resource_key)
    if asset is None:
        return None
    return sign_asset_download_url(session, asset)

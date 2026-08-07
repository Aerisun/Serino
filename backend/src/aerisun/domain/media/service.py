from __future__ import annotations

import hashlib
import logging
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.core.data_storage_lock import data_storage_cleanup_pending, data_storage_locked
from aerisun.core.settings import get_settings
from aerisun.core.time import shanghai_now
from aerisun.domain.exceptions import PayloadTooLarge, ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.exceptions import ValidationError as DomainValidationError
from aerisun.domain.iam.models import AdminSession
from aerisun.domain.media import repository as repo
from aerisun.domain.media.local_storage import write_local_asset_file
from aerisun.domain.media.models import Asset
from aerisun.domain.media.object_storage import (
    BitifulObjectStorageProvider,
    asset_admin_read_from_model,
    build_object_storage_maintenance_provider,
    build_object_storage_provider,
    get_or_create_object_storage_config,
    object_key_for_asset,
    process_local_asset_delete,
    process_remote_asset_delete,
    queue_asset_mirror,
    queue_local_asset_delete,
    queue_remote_asset_delete,
    should_use_direct_upload,
    sign_asset_download_url,
    upload_asset_bytes_to_remote,
)
from aerisun.domain.media.paths import (
    assert_managed_local_path,
    build_local_path,
    build_remote_object_key,
    build_resource_key,
    identity_from_resource_key,
    identity_from_upload,
    normalize_scope,
)
from aerisun.domain.media.preview_access import create_asset_preview_grant
from aerisun.domain.media.references import (
    ACTIVE_REFERENCE_FIELDS,
    build_legacy_url_variants,
    collect_registered_references,
)
from aerisun.domain.media.schemas import (
    AssetAdminRead,
    AssetAdminUpdate,
    AssetOpenUrlRead,
    AssetUploadCompleteWrite,
    AssetUploadPlanRead,
    AssetUploadPlanWrite,
)
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.waline.service import collect_waline_asset_references

logger = logging.getLogger(__name__)
_DEFAULT_COMMENT_IMAGE_UPLOAD_BYTES = 512 * 1024
_MAX_COMMENT_IMAGE_UPLOAD_BYTES = 2 * 1024 * 1024
_COMMENT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_COMMENT_IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_-]+")
_PUBLIC_SLUG_RE = re.compile(r"^[a-z0-9._-]+$")
_RESERVED_PUBLIC_SLUGS = {"public", "internal"}
_SAFE_FILE_STEM_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass(frozen=True, slots=True)
class AssetDeletionCleanup:
    asset_id: str
    resource_key: str
    file_name: str
    local_queue_item_id: str
    remote_queue_item_id: str | None


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
    return normalize_scope(value or "user")


def _normalize_note(value: str | None) -> str | None:
    note = (value or "").strip()
    return note or None


def _verify_remote_scope_copy(
    provider: BitifulObjectStorageProvider,
    *,
    object_key: str,
    asset: Asset,
    verification_path: Path,
) -> None:
    expected_sha256 = str(asset.sha256 or "").lower()
    if not expected_sha256:
        raise StateConflict("资源缺少 SHA-256，不能安全移动 OSS 范围")
    temporary = verification_path.with_name(f".{verification_path.name}.{secrets.token_hex(8)}.verify.tmp")
    try:
        provider.download_to_local(
            object_key=object_key,
            dest_path=temporary,
            bandwidth_limit_bps=None,
        )
        if asset.byte_size is not None and temporary.stat().st_size != asset.byte_size:
            raise StateConflict("资源范围移动后的 OSS 对象大小不一致")
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected_sha256:
            raise StateConflict("资源范围移动后的 OSS 对象摘要不一致")
    finally:
        temporary.unlink(missing_ok=True)


def _cleanup_prepared_scope_targets(
    session: Session,
    *,
    local_path: Path | None,
    remote_key: str | None,
    provider: BitifulObjectStorageProvider | None,
) -> None:
    queued_cleanup = False
    if local_path is not None:
        try:
            local_path.unlink(missing_ok=True)
        except Exception as exc:
            queue_local_asset_delete(session, storage_path=local_path)
            queued_cleanup = True
            logger.warning("Queued prepared local asset cleanup after immediate delete failed: %s", exc)
    if remote_key is not None and provider is not None:
        try:
            provider.delete_object(object_key=remote_key)
        except Exception as exc:
            queue_remote_asset_delete(
                session,
                object_key=remote_key,
                error=f"范围移动失败后的目标清理待重试：{exc}",
            )
            queued_cleanup = True
            logger.warning("Queued prepared remote asset cleanup after immediate delete failed: %s", exc)
    if queued_cleanup:
        session.commit()


def _normalize_public_slug(value: str | None) -> str | None:
    public_slug = (value or "").strip()
    if not public_slug:
        return None
    if public_slug in _RESERVED_PUBLIC_SLUGS:
        raise DomainValidationError("公开资源 slug 不能使用 public 或 internal")
    if "/" in public_slug or public_slug.lower() != public_slug or _PUBLIC_SLUG_RE.fullmatch(public_slug) is None:
        raise DomainValidationError("公开资源 slug 仅支持小写英文、数字、点、下划线和短横线")
    return public_slug


def _assert_public_slug_available(session: Session, public_slug: str | None, *, asset_id: str | None = None) -> None:
    if not public_slug:
        return
    existing_slug = repo.find_asset_by_public_slug(session, public_slug)
    if existing_slug is not None and existing_slug.id != asset_id:
        raise StateConflict("公开资源 slug 已存在")
    existing_resource = repo.find_asset_by_resource_key(session, public_slug)
    if existing_resource is not None and existing_resource.id != asset_id:
        raise StateConflict("公开资源 slug 与现有资源标识冲突")


def _apply_public_slug_to_existing_asset(
    session: Session,
    asset: Asset,
    public_slug: str | None,
) -> None:
    if not public_slug:
        return
    if asset.public_slug and asset.public_slug != public_slug:
        raise StateConflict("该资源已设置不同的公开 slug，请在资源编辑中修改")
    if asset.public_slug == public_slug:
        return
    _assert_public_slug_available(session, public_slug, asset_id=asset.id)
    asset.public_slug = public_slug


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


def _create_asset_record(
    session: Session,
    *,
    asset_id: str,
    file_name: str,
    resource_key: str,
    visibility: str,
    scope: str,
    category: str,
    note: str | None,
    public_slug: str | None,
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
        id=asset_id,
        file_name=file_name,
        resource_key=resource_key,
        visibility=visibility,
        scope=scope,
        category=category,
        note=note,
        public_slug=public_slug,
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
    public_slug: str | None = None,
) -> AssetAdminRead:
    from aerisun.domain.automation.events import emit_asset_uploaded

    normalized_visibility = _normalize_visibility(visibility)
    normalized_scope = _normalize_scope(scope)
    normalized_category = _normalize_category(category)
    normalized_note = _normalize_note(note)
    normalized_public_slug = _normalize_public_slug(public_slug)
    sha = hashlib.sha256(content).hexdigest()
    existing = repo.find_asset_by_fingerprint(
        session,
        sha256=sha,
        scope=normalized_scope,
        category=normalized_category,
    )
    if existing is not None:
        _apply_public_slug_to_existing_asset(session, existing, normalized_public_slug)
        storage_path = Path(existing.storage_path)
        if not storage_path.exists():
            provider = build_object_storage_provider(session)
            if (
                provider is not None
                and existing.storage_provider == "bitiful"
                and existing.remote_status == "available"
            ):
                queue_asset_mirror(session, existing)
                session.commit()
                session.refresh(existing)
            else:
                write_local_asset_file(storage_path, content, sha256=sha)
        if normalized_visibility == "public" and existing.visibility != "public":
            existing.visibility = "public"
        session.commit()
        session.refresh(existing)
        return asset_admin_read_from_model(existing)

    _assert_public_slug_available(session, normalized_public_slug)
    asset_id = uuid_str()
    identity = identity_from_upload(asset_id=asset_id, file_name=file_name, mime_type=mime_type)
    resource_key = build_resource_key(identity)
    storage_path = build_local_path(identity, normalized_scope)
    remote_object_key = build_remote_object_key(identity, normalized_scope)
    use_oss = build_object_storage_provider(session) is not None
    if use_oss:
        asset = _create_asset_record(
            session,
            asset_id=asset_id,
            file_name=file_name,
            resource_key=resource_key,
            visibility=normalized_visibility,
            scope=normalized_scope,
            category=normalized_category,
            note=normalized_note,
            public_slug=normalized_public_slug,
            storage_path=storage_path,
            mime_type=mime_type,
            byte_size=len(content),
            sha256=sha,
            storage_provider="bitiful",
            remote_object_key=remote_object_key,
            remote_status="available",
            mirror_status="queued",
            oss_acceleration_enabled_at_upload=True,
        )
        upload_asset_bytes_to_remote(session, asset=asset, content=content, mime_type=mime_type)
        queue_asset_mirror(session, asset)
    else:
        write_local_asset_file(storage_path, content, sha256=sha)
        asset = _create_asset_record(
            session,
            asset_id=asset_id,
            file_name=file_name,
            resource_key=resource_key,
            visibility=normalized_visibility,
            scope=normalized_scope,
            category=normalized_category,
            note=normalized_note,
            public_slug=normalized_public_slug,
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
    normalized_public_slug = _normalize_public_slug(payload.public_slug)
    existing = repo.find_asset_by_fingerprint(
        session,
        sha256=payload.sha256.lower(),
        scope=normalized_scope,
        category=normalized_category,
    )
    if existing is not None:
        if (
            existing.storage_provider == "bitiful"
            and existing.remote_status in {"pending_upload", "uploading", "none"}
            and not Path(existing.storage_path).is_file()
        ):
            provider = build_object_storage_provider(session)
            if provider is None:
                return AssetUploadPlanRead(mode="local")
            config = get_or_create_object_storage_config(session)
            expires_in = int(config.upload_expire_seconds or 300)
            upload_url = provider.sign_upload(
                object_key=object_key_for_asset(existing),
                content_type=existing.mime_type,
                expires_in=expires_in,
            )
            return AssetUploadPlanRead(
                mode="oss",
                asset_id=existing.id,
                resource_key=existing.resource_key,
                upload_url=upload_url,
                upload_method="PUT",
                upload_headers={},
                expires_at=shanghai_now() + timedelta(seconds=expires_in),
            )
        _apply_public_slug_to_existing_asset(session, existing, normalized_public_slug)
        if normalized_visibility == "public" and existing.visibility != "public":
            existing.visibility = "public"
        session.commit()
        session.refresh(existing)
        return AssetUploadPlanRead(mode="existing", asset=asset_admin_read_from_model(existing))

    _assert_public_slug_available(session, normalized_public_slug)
    provider = build_object_storage_provider(session)
    if provider is None or not should_use_direct_upload(session):
        return AssetUploadPlanRead(mode="local")

    asset_id = uuid_str()
    identity = identity_from_upload(asset_id=asset_id, file_name=payload.file_name, mime_type=payload.mime_type)
    resource_key = build_resource_key(identity)
    storage_path = build_local_path(identity, normalized_scope)
    remote_object_key = build_remote_object_key(identity, normalized_scope)
    asset = _create_asset_record(
        session,
        asset_id=asset_id,
        file_name=payload.file_name,
        resource_key=resource_key,
        visibility=normalized_visibility,
        scope=normalized_scope,
        category=normalized_category,
        note=normalized_note,
        public_slug=normalized_public_slug,
        storage_path=storage_path,
        mime_type=payload.mime_type,
        byte_size=payload.byte_size,
        sha256=payload.sha256.lower(),
        storage_provider="bitiful",
        remote_object_key=remote_object_key,
        remote_status="pending_upload",
        mirror_status="queued",
        oss_acceleration_enabled_at_upload=True,
    )
    config = get_or_create_object_storage_config(session)
    upload_url = provider.sign_upload(
        object_key=remote_object_key,
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
        expires_at=shanghai_now() + timedelta(seconds=int(config.upload_expire_seconds or 300)),
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

    head = provider.head_object(object_key=object_key_for_asset(asset))
    if head.content_length is None or (asset.byte_size is not None and head.content_length != asset.byte_size):
        try:
            provider.delete_object(object_key=object_key_for_asset(asset))
        except Exception as cleanup_exc:
            raise StateConflict(f"OSS 直传文件大小校验失败，且清理失败：{cleanup_exc}") from cleanup_exc
        raise StateConflict("OSS 直传文件大小与上传计划不一致，已清理，请重新上传")
    asset.storage_provider = "bitiful"
    asset.remote_status = "available"
    asset.remote_uploaded_at = shanghai_now()
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


def create_asset_open_url(
    session: Session,
    asset_id: str,
    *,
    admin_session: AdminSession,
) -> AssetOpenUrlRead:
    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")
    asset_read = asset_admin_read_from_model(asset)
    if asset.visibility == "public":
        return AssetOpenUrlRead(url=asset_read.internal_url)
    grant = create_asset_preview_grant(
        asset=asset,
        admin_session=admin_session,
    )
    return AssetOpenUrlRead(
        url=f"{asset_read.internal_url}?{urlencode({'preview_token': grant.token})}",
        expires_at=grant.expires_at,
    )


@data_storage_locked
def update_asset(session: Session, asset_id: str, payload: AssetAdminUpdate) -> AssetAdminRead:
    from aerisun.domain.automation.events import emit_asset_updated

    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")

    next_visibility = _normalize_visibility(payload.visibility or asset.visibility)
    next_scope = _normalize_scope(payload.scope or asset.scope)
    if next_scope != asset.scope and data_storage_cleanup_pending():
        raise StateConflict("资源迁移正在完成旧副本清理，请稍后再修改资源范围")
    next_category = _normalize_category(payload.category or asset.category)
    next_note = _normalize_note(payload.note if payload.note is not None else asset.note)
    if "public_slug" in payload.model_fields_set:
        next_public_slug = _normalize_public_slug(payload.public_slug)
    else:
        next_public_slug = asset.public_slug
    _assert_public_slug_available(session, next_public_slug, asset_id=asset.id)

    current_path = Path(asset.storage_path)
    previous_remote_object_key = str(asset.remote_object_key or "").strip() or None
    next_storage_path = current_path
    next_remote_object_key = previous_remote_object_key
    prepared_local_path: Path | None = None
    prepared_remote_key: str | None = None
    local_cleanup_queue_item_id: str | None = None
    remote_cleanup_queue_item_id: str | None = None
    provider = None

    if next_scope != asset.scope:
        identity = identity_from_resource_key(asset.resource_key)
        try:
            current_path = assert_managed_local_path(current_path)
            expected_current_path = build_local_path(identity, asset.scope)
        except DomainValidationError as exc:
            raise StateConflict("资源当前本地路径不安全，不能移动范围") from exc
        if current_path != expected_current_path:
            raise StateConflict("资源当前本地路径与范围不一致，不能移动范围")
        if previous_remote_object_key:
            expected_current_remote_key = build_remote_object_key(identity, asset.scope)
            if previous_remote_object_key != expected_current_remote_key:
                raise StateConflict("资源当前 OSS Key 与范围不一致，不能移动范围")
        next_storage_path = build_local_path(identity, next_scope)
        next_remote_object_key = build_remote_object_key(identity, next_scope) if previous_remote_object_key else None

        if current_path.exists() and next_storage_path != current_path:
            digest = asset.sha256 or hashlib.sha256(current_path.read_bytes()).hexdigest()
            next_storage_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = next_storage_path.with_name(f".{next_storage_path.name}.{secrets.token_hex(8)}.tmp")
            try:
                shutil.copyfile(current_path, temporary_path)
                if hashlib.sha256(temporary_path.read_bytes()).hexdigest() != digest:
                    raise StateConflict("资源范围移动后的本地文件摘要不一致")
                temporary_path.replace(next_storage_path)
                prepared_local_path = next_storage_path
            finally:
                temporary_path.unlink(missing_ok=True)

        if previous_remote_object_key and next_remote_object_key != previous_remote_object_key:
            provider = build_object_storage_maintenance_provider(session)
            if provider is None:
                _cleanup_prepared_scope_targets(
                    session,
                    local_path=prepared_local_path,
                    remote_key=None,
                    provider=None,
                )
                raise StateConflict("OSS 当前不可用，不能移动资源范围")
            try:
                head = provider.copy_object(
                    source_key=previous_remote_object_key,
                    object_key=next_remote_object_key,
                    content_type=asset.mime_type,
                )
                if asset.byte_size is not None and head.content_length != asset.byte_size:
                    raise StateConflict("资源范围移动后的 OSS 对象大小不一致")
                prepared_remote_key = next_remote_object_key
                _verify_remote_scope_copy(
                    provider,
                    object_key=next_remote_object_key,
                    asset=asset,
                    verification_path=next_storage_path,
                )
            except Exception as exc:
                _cleanup_prepared_scope_targets(
                    session,
                    local_path=prepared_local_path,
                    remote_key=next_remote_object_key,
                    provider=provider,
                )
                raise StateConflict(f"OSS 资源范围移动失败：{exc}") from exc

        asset.storage_path = str(next_storage_path)
        asset.remote_object_key = next_remote_object_key
        if prepared_local_path is not None and current_path != prepared_local_path:
            local_cleanup_queue_item_id = queue_local_asset_delete(session, storage_path=current_path)
        if prepared_remote_key is not None and previous_remote_object_key:
            remote_cleanup_queue_item_id = queue_remote_asset_delete(
                session,
                object_key=previous_remote_object_key,
            ).id

    asset.visibility = next_visibility
    asset.scope = next_scope
    asset.category = next_category
    asset.note = next_note
    asset.public_slug = next_public_slug
    try:
        session.commit()
    except Exception:
        session.rollback()
        _cleanup_prepared_scope_targets(
            session,
            local_path=prepared_local_path,
            remote_key=prepared_remote_key,
            provider=provider,
        )
        raise

    if local_cleanup_queue_item_id is not None:
        process_local_asset_delete(local_cleanup_queue_item_id)
    if remote_cleanup_queue_item_id is not None:
        process_remote_asset_delete(remote_cleanup_queue_item_id, provider=provider)
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


@data_storage_locked
def delete_asset(session: Session, asset_id: str) -> None:
    from aerisun.domain.automation.events import emit_asset_deleted

    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")
    if data_storage_cleanup_pending():
        raise StateConflict("资源迁移正在完成旧副本清理，请稍后再删除资源")
    _assert_asset_unused(session, asset)
    cleanup = _delete_asset_record(session, asset)
    session.commit()
    _process_asset_deletion_cleanup(session, cleanup)
    emit_asset_deleted(
        session,
        asset_id=cleanup.asset_id,
        resource_key=cleanup.resource_key,
        file_name=cleanup.file_name,
    )


def _active_asset_reference_locations(session: Session, asset: Asset) -> list[str]:
    settings = get_settings()
    urls = build_legacy_url_variants(asset, site_urls=(settings.site_url,))
    url_to_asset_id = {url: asset.id for url in urls}
    locations = {
        f"{reference.table}.{reference.column} row={reference.row_id}"
        for reference in collect_registered_references(
            session,
            url_to_asset_id,
            fields=ACTIVE_REFERENCE_FIELDS,
        )
    }
    locations.update(
        f"waline.wl_comment row={reference.row_id}"
        for reference in collect_waline_asset_references(settings.waline_db_path, url_to_asset_id)
    )
    return sorted(locations)


def _assert_asset_unused(session: Session, asset: Asset) -> None:
    locations = _active_asset_reference_locations(session, asset)
    if locations:
        raise StateConflict(f"资源仍被引用，不能删除：{locations[0]}")


def _delete_asset_record(session: Session, asset: Asset) -> AssetDeletionCleanup:
    path = Path(asset.storage_path)
    local_queue_item_id = queue_local_asset_delete(session, storage_path=path)
    remote_object_key = str(asset.remote_object_key or "").strip()
    remote_queue_item_id: str | None = None
    if remote_object_key:
        remote_queue_item_id = queue_remote_asset_delete(session, object_key=remote_object_key).id
    repo.delete_asset(session, asset)
    return AssetDeletionCleanup(
        asset_id=asset.id,
        resource_key=asset.resource_key,
        file_name=asset.file_name,
        local_queue_item_id=local_queue_item_id,
        remote_queue_item_id=remote_queue_item_id,
    )


def _process_asset_deletion_cleanup(session: Session, cleanup: AssetDeletionCleanup) -> None:
    process_local_asset_delete(cleanup.local_queue_item_id)
    if cleanup.remote_queue_item_id is not None:
        provider = build_object_storage_maintenance_provider(session)
        process_remote_asset_delete(cleanup.remote_queue_item_id, provider=provider)


@data_storage_locked
def bulk_delete_assets(session: Session, ids: list[str]) -> int:
    from aerisun.domain.automation.events import emit_asset_bulk_deleted

    if data_storage_cleanup_pending():
        raise StateConflict("资源迁移正在完成旧副本清理，请稍后再批量删除资源")
    assets = [asset for asset_id in ids if (asset := repo.find_asset_by_id(session, asset_id)) is not None]
    for asset in assets:
        _assert_asset_unused(session, asset)
    cleanup_items = [_delete_asset_record(session, asset) for asset in assets]
    affected = len(assets)
    session.commit()
    for cleanup in cleanup_items:
        _process_asset_deletion_cleanup(session, cleanup)
    emit_asset_bulk_deleted(session, ids=ids, affected=affected)
    return affected


def _normalize_image_mime_type(value: str | None) -> str:
    normalized = str(value or "").split(";", 1)[0].strip().lower()
    if normalized == "image/jpg":
        return "image/jpeg"
    return normalized


def _detect_comment_image_mime_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_comment_image_filename(filename: str, mime_type: str) -> str:
    raw_name = Path(filename or "image").name
    stem = Path(raw_name).stem.strip() or "image"
    stem = _SAFE_FILE_STEM_RE.sub("-", stem).strip(".-") or "image"
    return f"{stem[:80]}.{_COMMENT_IMAGE_EXTENSIONS[mime_type]}"


def get_comment_image_upload_limit(session: Session) -> int:
    community_config = site_config_repo.find_community_config(session)
    if community_config is not None and not community_config.image_uploader:
        raise DomainValidationError("当前站点已关闭评论图片上传。")
    configured_limit = int(community_config.image_max_bytes or 0) if community_config is not None else 0
    effective_limit = configured_limit if configured_limit > 0 else _DEFAULT_COMMENT_IMAGE_UPLOAD_BYTES
    return min(effective_limit, _MAX_COMMENT_IMAGE_UPLOAD_BYTES)


def save_comment_image(
    session: Session,
    content: bytes,
    filename: str,
    mime_type: str | None,
    *,
    uploader_id: str | None = None,
    surface: str = "comment",
) -> str:
    from aerisun.domain.automation.events import emit_comment_image_saved

    normalized_mime_type = _normalize_image_mime_type(mime_type)
    detected_mime_type = _detect_comment_image_mime_type(content)
    if normalized_mime_type not in _COMMENT_IMAGE_TYPES or detected_mime_type is None:
        raise DomainValidationError("不支持的图片格式")
    if detected_mime_type != normalized_mime_type:
        raise DomainValidationError("图片格式与文件内容不一致")

    effective_limit = get_comment_image_upload_limit(session)
    if len(content) > effective_limit:
        raise PayloadTooLarge("图片过大，请压缩后重试")
    normalized_surface = str(surface or "comment").strip().lower()
    if normalized_surface not in {"comment", "guestbook"}:
        raise DomainValidationError("访客图片来源仅支持 comment 或 guestbook")

    asset = upload_asset(
        session,
        _safe_comment_image_filename(filename, detected_mime_type),
        content,
        detected_mime_type,
        visibility="internal",
        scope="visitor",
        category=normalized_surface,
        note=f"site-user:{uploader_id}" if uploader_id else None,
    )
    emit_comment_image_saved(
        session,
        asset_id=asset.id,
        resource_key=asset.resource_key,
        file_name=asset.file_name,
    )
    return asset.internal_url


def resolve_media_redirect(session: Session, resource_key: str) -> str | None:
    asset = resolve_media_asset(session, resource_key)
    if asset is None:
        return None
    return sign_asset_download_url(session, asset)


def resolve_media_asset(session: Session, resource_key: str) -> Asset | None:
    key = str(resource_key or "").strip().lstrip("/")
    if key.startswith("assets/"):
        try:
            identity_from_resource_key(key)
        except DomainValidationError:
            return None
        return repo.find_asset_by_resource_key(session, key)
    if "/" not in key and key not in _RESERVED_PUBLIC_SLUGS:
        asset = repo.find_asset_by_public_slug(session, key)
        if asset is not None and asset.visibility == "public":
            return asset
    return None

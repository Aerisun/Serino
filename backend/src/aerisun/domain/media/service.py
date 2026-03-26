from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import PayloadTooLarge, ResourceNotFound
from aerisun.domain.exceptions import ValidationError as DomainValidationError
from aerisun.domain.media import repository as repo
from aerisun.domain.media.models import Asset
from aerisun.domain.media.schemas import AssetAdminRead, AssetAdminUpdate

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


def _guess_extension(file_name: str, mime_type: str | None) -> str:
    suffix = Path(file_name).suffix.lower().lstrip(".")
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed:
        return guessed.lstrip(".").lower()
    return "bin"


def _build_resource_key_from_digest(
    *,
    file_name: str,
    digest: str,
    mime_type: str | None,
    category: str,
    visibility: str,
) -> str:
    ext = _guess_extension(file_name, mime_type)
    return f"{visibility}/assets/{category}/{digest[:12]}.{ext}"


def _build_resource_key(*, file_name: str, content: bytes, mime_type: str | None, category: str, visibility: str) -> str:
    digest = hashlib.sha256(content).hexdigest()
    return _build_resource_key_from_digest(
        file_name=file_name,
        digest=digest,
        mime_type=mime_type,
        category=category,
        visibility=visibility,
    )


def _resource_urls(resource_key: str, visibility: str) -> tuple[str, str | None]:
    asset_url = f"/media/{resource_key}"
    public_url = asset_url if visibility == "public" else None
    return asset_url, public_url


def _asset_to_read(asset: Asset) -> AssetAdminRead:
    internal_url, public_url = _resource_urls(asset.resource_key, asset.visibility)
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
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def list_assets(session: Session, page: int = 1, page_size: int = 20, q: str | None = None, scope: str | None = None) -> dict:
    items, total = repo.find_assets_paginated(session, page=page, page_size=page_size, q=q, scope=scope)
    return {
        "items": [_asset_to_read(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)

    normalized_visibility = _normalize_visibility(visibility)
    normalized_scope = _normalize_scope(scope)
    normalized_category = _normalize_category(category)
    normalized_note = _normalize_note(note)
    sha = hashlib.sha256(content).hexdigest()
    resource_key = _build_resource_key(
        file_name=file_name,
        content=content,
        mime_type=mime_type,
        category=normalized_category,
        visibility=normalized_visibility,
    )
    storage_path = media_dir / resource_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    if not storage_path.exists():
        with open(storage_path, "wb") as f:
            f.write(content)

    asset = repo.create_asset(
        session,
        file_name=file_name,
        resource_key=resource_key,
        visibility=normalized_visibility,
        scope=normalized_scope,
        category=normalized_category,
        note=normalized_note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=sha,
    )
    session.commit()
    session.refresh(asset)
    return _asset_to_read(asset)


def update_asset(session: Session, asset_id: str, payload: AssetAdminUpdate) -> AssetAdminRead:
    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")

    next_visibility = _normalize_visibility(payload.visibility or asset.visibility)
    next_scope = _normalize_scope(payload.scope or asset.scope)
    next_category = _normalize_category(payload.category or asset.category)
    next_note = _normalize_note(payload.note if payload.note is not None else asset.note)

    digest = asset.sha256
    if not digest:
        storage_path = Path(asset.storage_path)
        if not storage_path.exists():
            raise DomainValidationError("资源文件不存在，无法更新")
        digest = hashlib.sha256(storage_path.read_bytes()).hexdigest()

    next_resource_key = _build_resource_key_from_digest(
        file_name=asset.file_name,
        digest=digest,
        mime_type=asset.mime_type,
        category=next_category,
        visibility=next_visibility,
    )

    if next_resource_key != asset.resource_key:
        existing = repo.find_asset_by_resource_key(session, next_resource_key)
        if existing is not None and existing.id != asset.id:
            raise DomainValidationError("目标资源标识已存在")

        settings = get_settings()
        media_dir = settings.media_dir.expanduser().resolve()
        media_dir.mkdir(parents=True, exist_ok=True)

        current_path = Path(asset.storage_path)
        if not current_path.exists():
            raise DomainValidationError("资源文件不存在，无法更新")

        next_storage_path = media_dir / next_resource_key
        next_storage_path.parent.mkdir(parents=True, exist_ok=True)
        if next_storage_path.exists() and next_storage_path != current_path:
            raise DomainValidationError("目标资源路径已存在")
        if next_storage_path != current_path:
            current_path.replace(next_storage_path)
            asset.storage_path = str(next_storage_path)

        asset.resource_key = next_resource_key

    asset.visibility = next_visibility
    asset.scope = next_scope
    asset.category = next_category
    asset.note = next_note
    session.commit()
    session.refresh(asset)
    return _asset_to_read(asset)


def get_asset(session: Session, asset_id: str) -> AssetAdminRead:
    obj = repo.find_asset_by_id(session, asset_id)
    if obj is None:
        raise ResourceNotFound("Asset not found")
    return _asset_to_read(obj)


def delete_asset(session: Session, asset_id: str) -> None:
    asset = repo.find_asset_by_id(session, asset_id)
    if asset is None:
        raise ResourceNotFound("Asset not found")
    path = Path(asset.storage_path)
    if path.exists():
        path.unlink()
    repo.delete_asset(session, asset)
    session.commit()


def bulk_delete_assets(session: Session, ids: list[str]) -> int:
    affected = repo.delete_assets_by_ids(session, ids)
    session.commit()
    return affected


def save_comment_image(session: Session, content: bytes, filename: str, mime_type: str | None) -> str:
    """Save a comment image as a user asset and return its public URL path."""
    if mime_type not in _ALLOWED_IMAGE_TYPES:
        raise DomainValidationError("不支持的图片格式")
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
    return asset.internal_url

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.media.models import Asset
from aerisun.domain.media.schemas import AssetAdminRead

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def list_assets(session: Session, page: int = 1, page_size: int = 20) -> dict:
    q = session.query(Asset)
    total = q.count()
    items = q.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [AssetAdminRead.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def upload_asset(session: Session, file_name: str, content: bytes, mime_type: str | None) -> AssetAdminRead:
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content).hexdigest()
    storage_path = str(media_dir / f"{sha[:12]}_{file_name}")

    with open(storage_path, "wb") as f:
        f.write(content)

    asset = Asset(
        file_name=file_name,
        storage_path=storage_path,
        mime_type=mime_type,
        byte_size=len(content),
        sha256=sha,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return AssetAdminRead.model_validate(asset)


def get_asset(session: Session, asset_id: str) -> AssetAdminRead:
    obj = session.get(Asset, asset_id)
    if obj is None:
        raise LookupError("Asset not found")
    return AssetAdminRead.model_validate(obj)


def delete_asset(session: Session, asset_id: str) -> None:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise LookupError("Asset not found")
    path = Path(asset.storage_path)
    if path.exists():
        path.unlink()
    session.delete(asset)
    session.commit()


def bulk_delete_assets(session: Session, ids: list[str]) -> int:
    affected = session.query(Asset).filter(Asset.id.in_(ids)).delete(synchronize_session="fetch")
    session.commit()
    return affected


def save_comment_image(content: bytes, filename: str, mime_type: str | None) -> str:
    """Save comment image to disk and return public URL path.
    Raises ValueError for unsupported type or oversized files.
    """
    if mime_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError("不支持的图片格式")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ValueError("图片过大，请压缩后重试")

    settings = get_settings()
    media_dir = Path(settings.media_dir).expanduser().resolve() / "comment-images"
    media_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content).hexdigest()[:12]
    ext = (filename or "img").rsplit(".", 1)[-1] if filename else "jpg"
    dest_filename = f"{sha}.{ext}"
    dest = media_dir / dest_filename

    if not dest.exists():
        with open(dest, "wb") as f:
            f.write(content)

    return f"/media/comment-images/{dest_filename}"

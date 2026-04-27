from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.media import repository as media_repo
from aerisun.domain.media.service import resolve_media_redirect

router = APIRouter()


def _media_root() -> Path:
    return get_settings().media_dir.expanduser().resolve()


def _normalize_media_local_path(candidate: Path) -> Path:
    media_root = _media_root()
    normalized = candidate.expanduser().resolve()
    try:
        normalized.relative_to(media_root)
    except ValueError as exc:
        raise ResourceNotFound("Media resource not found") from exc
    return normalized


def _resolve_local_path(resource_key: str) -> Path:
    media_root = get_settings().media_dir.expanduser().resolve()
    return _normalize_media_local_path(media_root / resource_key)


def _serve_local_path(resource_key: str, *, session: Session) -> Response:
    asset = media_repo.find_asset_by_resource_key(session, resource_key)
    if asset is not None:
        local_path = _normalize_media_local_path(Path(asset.storage_path))
    else:
        if not resource_key.startswith("public/"):
            raise ResourceNotFound("Media resource not found")
        local_path = _resolve_local_path(resource_key)
    if not local_path.exists() or not local_path.is_file():
        raise ResourceNotFound("Media resource not found")
    media_type = asset.mime_type if asset is not None else None
    return FileResponse(local_path, media_type=media_type)


@router.get("/media/{resource_key:path}", summary="托管资源访问网关")
@router.head("/media/{resource_key:path}", summary="托管资源访问网关")
def serve_media(
    resource_key: str,
    session: Session = Depends(get_session),
) -> Response:
    redirect_url = resolve_media_redirect(session, resource_key)
    if redirect_url:
        return RedirectResponse(url=redirect_url, status_code=307)
    return _serve_local_path(resource_key, session=session)

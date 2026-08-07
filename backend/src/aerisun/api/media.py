from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import PermissionDenied, ResourceNotFound, ValidationError
from aerisun.domain.media.models import Asset
from aerisun.domain.media.object_storage import sign_asset_download_url
from aerisun.domain.media.paths import assert_managed_local_path, build_local_path, identity_from_asset
from aerisun.domain.media.preview_access import validate_asset_preview_grant
from aerisun.domain.media.service import resolve_media_asset

router = APIRouter()


def _media_root() -> Path:
    return get_settings().media_dir.expanduser().resolve()


def _serve_local_asset(asset: Asset) -> Response:
    try:
        local_path = assert_managed_local_path(Path(asset.storage_path))
        expected_path = build_local_path(identity_from_asset(asset), asset.scope)
    except ValidationError as exc:
        raise ResourceNotFound("Media resource not found") from exc
    if local_path != expected_path:
        raise ResourceNotFound("Media resource not found")
    if not local_path.exists() or not local_path.is_file():
        raise ResourceNotFound("Media resource not found")
    return FileResponse(local_path, media_type=asset.mime_type)


def _origin(value: str) -> tuple[str, str, int | None] | None:
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, parsed.hostname.lower(), port


def _internal_asset_request_allowed(request: Request) -> bool:
    fetch_site = str(request.headers.get("sec-fetch-site") or "").strip().lower()
    fetch_mode = str(request.headers.get("sec-fetch-mode") or "").strip().lower()
    fetch_dest = str(request.headers.get("sec-fetch-dest") or "").strip().lower()
    if fetch_site:
        return fetch_site == "same-origin" and fetch_mode != "navigate" and fetch_dest != "document"

    expected_origin = _origin(get_settings().site_url)
    if expected_origin is None:
        return False
    supplied_origin = _origin(request.headers.get("origin") or "")
    if supplied_origin is None:
        supplied_origin = _origin(request.headers.get("referer") or "")
    return supplied_origin == expected_origin


def _apply_internal_response_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Sec-Fetch-Site, Sec-Fetch-Mode, Sec-Fetch-Dest"
    return response


@router.get("/media/{resource_key:path}", summary="托管资源访问网关")
@router.head("/media/{resource_key:path}", summary="托管资源访问网关")
def serve_media(
    resource_key: str,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    asset = resolve_media_asset(session, resource_key)
    if asset is None:
        raise ResourceNotFound("Media resource not found")
    preview_allowed = asset.visibility == "internal" and validate_asset_preview_grant(
        session,
        asset=asset,
        token=request.query_params.get("preview_token"),
    )
    if asset.visibility == "internal" and not preview_allowed and not _internal_asset_request_allowed(request):
        raise PermissionDenied("该资源仅允许站内页面加载")

    redirect_url = sign_asset_download_url(session, asset)
    if redirect_url:
        response: Response = RedirectResponse(url=redirect_url, status_code=307)
    else:
        response = _serve_local_asset(asset)
    if asset.visibility == "internal":
        return _apply_internal_response_headers(response)
    return response

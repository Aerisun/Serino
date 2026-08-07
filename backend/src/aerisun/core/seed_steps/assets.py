from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.media import repository as media_repo
from aerisun.domain.media.local_storage import write_local_asset_file
from aerisun.domain.media.models import Asset
from aerisun.domain.media.paths import build_local_path, build_resource_key, identity_from_upload


def purge_managed_media_root() -> None:
    media_dir = get_settings().media_dir.expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    if media_dir == media_dir.parent:
        raise RuntimeError(f"Refusing to purge unsafe media root: {media_dir}")
    for child in media_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def ensure_seed_content_asset(
    session: Session,
    *,
    file_name: str,
    content: bytes,
    mime_type: str | None,
    category: str,
    visibility: str = "internal",
    note: str | None = None,
) -> str:
    sha256 = hashlib.sha256(content).hexdigest()
    existing = media_repo.find_asset_by_fingerprint(
        session,
        sha256=sha256,
        scope="system",
        category=category,
    )
    if existing is not None:
        if visibility == "public":
            existing.visibility = "public"
        if note and not existing.note:
            existing.note = note
        session.flush()
        return f"/media/{existing.resource_key}"

    asset_id = str(uuid5(NAMESPACE_URL, f"serino-system-asset:{category}:{sha256}"))
    identity = identity_from_upload(asset_id=asset_id, file_name=file_name, mime_type=mime_type)
    resource_key = build_resource_key(identity)
    storage_path = build_local_path(identity, "system")
    write_local_asset_file(storage_path, content, sha256=sha256)

    asset = Asset(
        id=asset_id,
        file_name=file_name,
        resource_key=resource_key,
        visibility=visibility,
        scope="system",
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=sha256,
    )
    session.add(asset)
    session.flush()
    return f"/media/{asset.resource_key}"


def build_seed_avatar_svg(label: str) -> bytes:
    initials = (label.strip()[:2] or "A").upper()
    color_seed = hashlib.sha256(label.encode("utf-8")).hexdigest()[:6]
    bg = f"#{color_seed}"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"
viewBox="0 0 256 256" role="img" aria-label="{label}">
<rect width="256" height="256" rx="56" fill="{bg}"/>
<text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle"
font-family="Inter, Arial, sans-serif" font-size="88" font-weight="700" fill="white">{initials}</text>
</svg>'''
    return svg.encode("utf-8")


def ensure_seed_asset(
    session: Session,
    *,
    source_path: Path,
    category: str,
    visibility: str = "internal",
    public_slug: str | None = None,
    note: str | None = None,
) -> str:
    if not source_path.exists():
        return ""

    content = source_path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    slug_owner = session.query(Asset).filter(Asset.public_slug == public_slug).first() if public_slug else None
    if slug_owner is not None and (
        str(slug_owner.sha256 or "").lower() != sha256
        or slug_owner.scope != "system"
        or slug_owner.category != category
    ):
        raise RuntimeError(f"Public asset slug is already in use: {public_slug}")
    existing = media_repo.find_asset_by_fingerprint(
        session,
        sha256=sha256,
        scope="system",
        category=category,
    )
    if slug_owner is not None:
        existing = slug_owner
    if existing is not None:
        if existing.visibility != visibility:
            existing.visibility = visibility
        if public_slug:
            existing.public_slug = public_slug
        if note and not existing.note:
            existing.note = note
        session.flush()
        return f"/media/{existing.resource_key}"

    mime_type, _ = mimetypes.guess_type(source_path.name)
    asset_id = str(uuid5(NAMESPACE_URL, f"serino-system-asset:{category}:{sha256}"))
    identity = identity_from_upload(asset_id=asset_id, file_name=source_path.name, mime_type=mime_type)
    resource_key = build_resource_key(identity)
    storage_path = build_local_path(identity, "system")
    write_local_asset_file(storage_path, content, sha256=sha256)
    asset = Asset(
        id=asset_id,
        file_name=source_path.name,
        resource_key=resource_key,
        visibility=visibility,
        public_slug=public_slug,
        scope="system",
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=sha256,
    )
    session.add(asset)
    session.flush()
    return f"/media/{asset.resource_key}"


def ensure_system_asset_reference(
    session: Session,
    *,
    source_value: str | None,
    category: str,
    note: str | None = None,
    source_roots: list[Path] | tuple[Path, ...] | None = None,
    timeout_seconds: float = 20.0,
) -> str:
    value = str(source_value or "").strip()
    if not value:
        return ""

    if value.startswith("/media/"):
        resource_key = value.removeprefix("/media/").strip("/")
        asset = session.query(Asset).filter(Asset.resource_key == resource_key).first()
        if asset is None:
            return value

        if note and not asset.note:
            asset.note = note
        session.flush()
        return f"/media/{asset.resource_key}"

    if value.startswith("/"):
        candidate_roots: list[Path] = []
        for root in source_roots or ():
            resolved_root = root.expanduser().resolve()
            if resolved_root not in candidate_roots:
                candidate_roots.append(resolved_root)

        for root in candidate_roots:
            candidate = (root / value.lstrip("/")).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if candidate.exists() and candidate.is_file():
                return ensure_seed_asset(session, source_path=candidate, category=category, note=note)

    return value

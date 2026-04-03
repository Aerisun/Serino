from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.media.models import Asset


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
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    digest = hashlib.sha256(content).hexdigest()[:12]
    guessed_ext = mimetypes.guess_extension(mime_type or "") or ".bin"
    ext = Path(file_name).suffix.lower().lstrip(".") or guessed_ext.lstrip(".")
    resource_key = f"{visibility}/assets/{category}/{digest}.{ext}"
    existing = session.query(Asset).filter(Asset.resource_key == resource_key).first()
    if existing is not None:
        if existing.scope != "system":
            existing.scope = "system"
        if note and not existing.note:
            existing.note = note
        session.flush()
        return f"/media/{existing.resource_key}"

    storage_path = media_dir / resource_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists():
        storage_path.write_bytes(content)

    asset = Asset(
        file_name=file_name,
        resource_key=resource_key,
        visibility=visibility,
        scope="system",
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
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
    note: str | None = None,
) -> str:
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    if not source_path.exists():
        return ""

    content = source_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()[:12]
    ext = source_path.suffix.lower().lstrip(".") or "bin"
    resource_key = f"{visibility}/assets/{category}/{digest}.{ext}"
    existing = session.query(Asset).filter(Asset.resource_key == resource_key).first()
    if existing is not None:
        if existing.scope != "system":
            existing.scope = "system"
        if note and not existing.note:
            existing.note = note
        session.flush()
        return f"/media/{existing.resource_key}"

    storage_path = media_dir / resource_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists():
        storage_path.write_bytes(content)

    mime_type, _ = mimetypes.guess_type(source_path.name)
    asset = Asset(
        file_name=source_path.name,
        resource_key=resource_key,
        visibility=visibility,
        scope="system",
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
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
            storage_path = get_settings().media_dir.expanduser().resolve() / resource_key
            if not storage_path.exists():
                return value

            mime_type, _ = mimetypes.guess_type(storage_path.name)
            visibility = resource_key.split("/", 1)[0] if "/" in resource_key else "internal"
            resource_parts = resource_key.split("/")
            inferred_category = (
                resource_parts[2] if len(resource_parts) >= 4 and resource_parts[1] == "assets" else category
            )
            asset = Asset(
                file_name=storage_path.name,
                resource_key=resource_key,
                visibility=visibility,
                scope="system",
                category=inferred_category,
                note=note,
                storage_path=str(storage_path),
                mime_type=mime_type,
                byte_size=storage_path.stat().st_size,
                sha256=hashlib.sha256(storage_path.read_bytes()).hexdigest(),
            )
            session.add(asset)
            session.flush()
            return f"/media/{asset.resource_key}"

        if asset.scope != "system":
            asset.scope = "system"
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

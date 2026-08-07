from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import ValidationError

AssetScope = Literal["user", "article", "visitor", "system"]
ASSET_SCOPES: tuple[AssetScope, ...] = ("user", "article", "visitor", "system")

_SAFE_ASSET_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_EXTENSION_RE = re.compile(r"^[a-z0-9]{1,16}$")


@dataclass(frozen=True, slots=True)
class AssetIdentity:
    asset_id: str
    extension: str

    def __post_init__(self) -> None:
        if _SAFE_ASSET_ID_RE.fullmatch(self.asset_id) is None:
            raise ValidationError("资源 ID 不合法")
        if _SAFE_EXTENSION_RE.fullmatch(self.extension) is None:
            raise ValidationError("资源扩展名不合法")


class AssetLike(Protocol):
    id: str
    file_name: str
    mime_type: str | None
    resource_key: str


def normalize_scope(value: str | None) -> AssetScope:
    scope = str(value or "").strip()
    if scope not in ASSET_SCOPES:
        raise ValidationError("资源范围仅支持 user、article、visitor 或 system")
    return cast(AssetScope, scope)


def guess_extension(file_name: str, mime_type: str | None) -> str:
    suffix = Path(file_name or "").suffix.lower().lstrip(".")
    if suffix and _SAFE_EXTENSION_RE.fullmatch(suffix):
        return suffix
    guessed = mimetypes.guess_extension(str(mime_type or "").split(";", 1)[0].strip().lower())
    extension = str(guessed or ".bin").lstrip(".").lower()
    if extension == "jpe":
        extension = "jpg"
    if _SAFE_EXTENSION_RE.fullmatch(extension) is None:
        return "bin"
    return extension


def identity_from_upload(*, asset_id: str, file_name: str, mime_type: str | None) -> AssetIdentity:
    return AssetIdentity(asset_id=asset_id, extension=guess_extension(file_name, mime_type))


def identity_from_asset(asset: AssetLike) -> AssetIdentity:
    resource_name = Path(str(asset.resource_key or "")).name
    extension = Path(resource_name).suffix.lower().lstrip(".")
    if not extension:
        extension = guess_extension(asset.file_name, asset.mime_type)
    return AssetIdentity(asset_id=str(asset.id), extension=extension)


def build_resource_key(identity: AssetIdentity) -> str:
    return f"assets/{identity.asset_id}.{identity.extension}"


def identity_from_resource_key(resource_key: str) -> AssetIdentity:
    normalized = str(resource_key or "").strip().lstrip("/")
    parts = normalized.split("/")
    if len(parts) != 2 or parts[0] != "assets" or "." not in parts[1]:
        raise ValidationError("资源永久标识不合法")
    asset_id, extension = parts[1].rsplit(".", 1)
    identity = AssetIdentity(asset_id=asset_id, extension=extension)
    if build_resource_key(identity) != normalized:
        raise ValidationError("资源永久标识不合法")
    return identity


def build_media_url(identity: AssetIdentity) -> str:
    return f"/media/{build_resource_key(identity)}"


def build_remote_object_key(identity: AssetIdentity, scope: str) -> str:
    normalized_scope = normalize_scope(scope)
    return f"assets/{normalized_scope}/{identity.asset_id}.{identity.extension}"


def _managed_media_root() -> Path:
    return get_settings().media_dir.expanduser().resolve() / "assets"


def build_local_path(identity: AssetIdentity, scope: str) -> Path:
    normalized_scope = normalize_scope(scope)
    return assert_managed_local_path(
        _managed_media_root() / normalized_scope / f"{identity.asset_id}.{identity.extension}"
    )


def assert_managed_local_path(path: Path) -> Path:
    root = _managed_media_root()
    candidate = path.expanduser().resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError("资源文件路径超出受管目录") from exc
    if len(relative.parts) != 2:
        raise ValidationError("资源文件路径层级不合法")
    normalize_scope(relative.parts[0])
    file_path = relative.parts[1]
    if "." not in file_path:
        raise ValidationError("资源文件名缺少扩展名")
    asset_id, extension = file_path.rsplit(".", 1)
    AssetIdentity(asset_id=asset_id, extension=extension)
    return candidate


def assert_managed_object_key(key: str) -> str:
    normalized = str(key or "").strip().lstrip("/")
    parts = normalized.split("/")
    if len(parts) != 3 or parts[0] != "assets":
        raise ValidationError("OSS 资源 Key 不在受管目录")
    normalize_scope(parts[1])
    if "." not in parts[2]:
        raise ValidationError("OSS 资源 Key 缺少扩展名")
    asset_id, extension = parts[2].rsplit(".", 1)
    AssetIdentity(asset_id=asset_id, extension=extension)
    return normalized

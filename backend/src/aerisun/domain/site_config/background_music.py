from __future__ import annotations

from pathlib import Path

from aerisun.domain.exceptions import PayloadTooLarge, ValidationError
from aerisun.domain.media.models import Asset

BACKGROUND_MUSIC_MAX_BYTES = 50 * 1024 * 1024
BACKGROUND_MUSIC_MIME_TYPES = {"audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/m4a", "audio/aac"}
BACKGROUND_MUSIC_EXTENSIONS = {".mp3", ".m4a", ".aac"}


def _normalized_music_mime_type(value: str | None) -> str:
    return str(value or "").split(";", 1)[0].strip().lower()


def is_background_music_asset_playable(asset: Asset) -> bool:
    suffix = Path(asset.file_name or asset.resource_key).suffix.lower()
    byte_size = int(asset.byte_size or 0)
    return (
        asset.visibility == "public"
        and asset.scope == "system"
        and asset.category == "music"
        and _normalized_music_mime_type(asset.mime_type) in BACKGROUND_MUSIC_MIME_TYPES
        and suffix in BACKGROUND_MUSIC_EXTENSIONS
        and 0 < byte_size <= BACKGROUND_MUSIC_MAX_BYTES
    )


def validate_background_music_asset(asset: Asset) -> None:
    if not is_background_music_asset_playable(asset):
        raise ValidationError("请选择公开音乐资源：仅支持 system/music 下不超过 50 MiB 的 MP3、M4A 或 AAC 文件")


def validate_background_music_upload(
    *,
    file_name: str,
    byte_size: int,
    mime_type: str | None,
    visibility: str,
    scope: str,
    category: str,
) -> None:
    if category != "music":
        return
    if byte_size > BACKGROUND_MUSIC_MAX_BYTES:
        raise PayloadTooLarge("背景音乐单个文件不能超过 50 MiB")
    suffix = Path(file_name).suffix.lower()
    normalized_mime = _normalized_music_mime_type(mime_type)
    if suffix not in BACKGROUND_MUSIC_EXTENSIONS or normalized_mime not in BACKGROUND_MUSIC_MIME_TYPES:
        raise ValidationError("背景音乐仅支持 MP3、M4A 或 AAC 文件")
    if visibility != "public" or scope != "system":
        raise ValidationError("背景音乐必须作为公开的 system/music 资源上传")

from __future__ import annotations

from aerisun import __version__ as package_version
from aerisun.core.settings import Settings, get_settings


def get_runtime_version(settings: Settings | None = None) -> str:
    resolved_settings = settings or get_settings()
    release_version = (resolved_settings.release_version or "").strip()
    return release_version or package_version

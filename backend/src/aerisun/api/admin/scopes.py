"""API key scope constants and validation."""

from __future__ import annotations

# Scope constants
CONTENT_READ = "content:read"
CONTENT_WRITE = "content:write"
SYSTEM_READ = "system:read"
SYSTEM_WRITE = "system:write"
ASSETS_READ = "assets:read"
ASSETS_WRITE = "assets:write"
CONFIG_READ = "config:read"
CONFIG_WRITE = "config:write"

ALL_SCOPES = [
    CONTENT_READ,
    CONTENT_WRITE,
    SYSTEM_READ,
    SYSTEM_WRITE,
    ASSETS_READ,
    ASSETS_WRITE,
    CONFIG_READ,
    CONFIG_WRITE,
]

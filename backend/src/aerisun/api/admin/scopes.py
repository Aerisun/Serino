"""API key scope constants and validation."""

from __future__ import annotations

# Scope constants
AGENT_CONNECT = "agent:connect"
CONTENT_READ = "content:read"
CONTENT_WRITE = "content:write"
MODERATION_READ = "moderation:read"
MODERATION_WRITE = "moderation:write"
SYSTEM_READ = "system:read"
SYSTEM_WRITE = "system:write"
ASSETS_READ = "assets:read"
ASSETS_WRITE = "assets:write"
CONFIG_READ = "config:read"
CONFIG_WRITE = "config:write"
SUBSCRIPTIONS_READ = "subscriptions:read"
SUBSCRIPTIONS_WRITE = "subscriptions:write"
VISITORS_READ = "visitors:read"
VISITORS_WRITE = "visitors:write"
AUTH_READ = "auth:read"
AUTH_WRITE = "auth:write"
AUTOMATION_READ = "automation:read"
AUTOMATION_WRITE = "automation:write"
NETWORK_READ = "network:read"
NETWORK_WRITE = "network:write"

ALL_SCOPES = [
    AGENT_CONNECT,
    CONTENT_READ,
    CONTENT_WRITE,
    MODERATION_READ,
    MODERATION_WRITE,
    SYSTEM_READ,
    SYSTEM_WRITE,
    ASSETS_READ,
    ASSETS_WRITE,
    CONFIG_READ,
    CONFIG_WRITE,
    SUBSCRIPTIONS_READ,
    SUBSCRIPTIONS_WRITE,
    VISITORS_READ,
    VISITORS_WRITE,
    AUTH_READ,
    AUTH_WRITE,
    AUTOMATION_READ,
    AUTOMATION_WRITE,
    NETWORK_READ,
    NETWORK_WRITE,
]

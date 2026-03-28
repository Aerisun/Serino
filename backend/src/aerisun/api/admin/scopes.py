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
MCP_CONNECT = "mcp:connect"
MCP_CONTENT_READ = "mcp:content:read"
MCP_CONTENT_WRITE = "mcp:content:write"
MCP_MODERATION_READ = "mcp:moderation:read"
MCP_MODERATION_WRITE = "mcp:moderation:write"
MCP_CONFIG_READ = "mcp:config:read"
MCP_CONFIG_WRITE = "mcp:config:write"
MCP_ASSETS_READ = "mcp:assets:read"
MCP_ASSETS_WRITE = "mcp:assets:write"

ALL_SCOPES = [
    CONTENT_READ,
    CONTENT_WRITE,
    SYSTEM_READ,
    SYSTEM_WRITE,
    ASSETS_READ,
    ASSETS_WRITE,
    CONFIG_READ,
    CONFIG_WRITE,
    MCP_CONNECT,
    MCP_CONTENT_READ,
    MCP_CONTENT_WRITE,
    MCP_MODERATION_READ,
    MCP_MODERATION_WRITE,
    MCP_CONFIG_READ,
    MCP_CONFIG_WRITE,
    MCP_ASSETS_READ,
    MCP_ASSETS_WRITE,
]

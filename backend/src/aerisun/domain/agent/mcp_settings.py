from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import (
    MCP_ASSETS_READ,
    MCP_ASSETS_WRITE,
    MCP_CONFIG_READ,
    MCP_CONFIG_WRITE,
    MCP_CONNECT,
    MCP_CONTENT_READ,
    MCP_CONTENT_WRITE,
    MCP_MODERATION_READ,
    MCP_MODERATION_WRITE,
)
from aerisun.domain.agent.capability_ids import build_capability_id
from aerisun.domain.agent.schemas import AgentUsageCapabilityRead, McpPresetRead
from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.site_config import repository as site_repo

if TYPE_CHECKING:
    from aerisun.domain.iam.models import ApiKey

CUSTOM_MCP_PRESET = "custom"
DEFAULT_MCP_PRESET = "readonly"
MCP_CONFIG_FLAG_KEY = "mcp_config"


@dataclass(slots=True)
class McpResolvedConfig:
    public_access: bool
    enabled_capability_ids: list[str]
    selected_preset: str
    is_customized: bool
    presets: list[McpPresetRead]


def _get_site_profile(session: Session):
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return profile


def _read_site_feature_flags(session: Session) -> tuple[object, dict[str, object]]:
    profile = _get_site_profile(session)
    feature_flags = dict(profile.feature_flags or {})
    return profile, feature_flags


def filter_capabilities_for_scopes(
    capabilities: list[AgentUsageCapabilityRead],
    available_scopes: list[str] | None,
) -> list[AgentUsageCapabilityRead]:
    if available_scopes is None:
        return list(capabilities)
    allowed = set(available_scopes)
    return [item for item in capabilities if all(scope in allowed for scope in (item.required_scopes or []))]


def _capability_ids_without_write_scopes(capabilities: list[AgentUsageCapabilityRead]) -> list[str]:
    return [
        item.id for item in capabilities if not any(scope.endswith(":write") for scope in (item.required_scopes or []))
    ]


def _capability_ids_for_allowed_scopes(
    capabilities: list[AgentUsageCapabilityRead],
    *,
    allowed_scopes: set[str],
) -> list[str]:
    return [
        item.id
        for item in capabilities
        if all(scope in allowed_scopes or not scope.endswith(":write") for scope in (item.required_scopes or []))
    ]


def _preset_map(presets: list[McpPresetRead]) -> dict[str, McpPresetRead]:
    return {preset.key: preset for preset in presets}


def build_mcp_presets(capabilities: list[AgentUsageCapabilityRead]) -> list[McpPresetRead]:
    readonly_ids = _capability_ids_without_write_scopes(capabilities)
    basic_management_ids = _capability_ids_for_allowed_scopes(
        capabilities,
        allowed_scopes={MCP_CONTENT_WRITE, MCP_MODERATION_WRITE},
    )
    full_ids = [item.id for item in capabilities]

    return [
        McpPresetRead(
            key=DEFAULT_MCP_PRESET,
            name="只读档次",
            description="开放这个 API Key 当前可用的读取类 MCP 能力。",
            capability_ids=readonly_ids,
        ),
        McpPresetRead(
            key="basic_management",
            name="初级管理档次",
            description="在只读基础上开放内容编辑、发布、可见性调整，以及评论和留言审核。",
            capability_ids=basic_management_ids,
        ),
        McpPresetRead(
            key="full_management",
            name="全面管理档次",
            description="开放这个 API Key 当前 scope 允许的全部 MCP 管理能力。",
            capability_ids=full_ids,
        ),
    ]


def normalize_enabled_capability_ids(
    raw_ids: list[str] | None,
    capabilities: list[AgentUsageCapabilityRead],
    *,
    default_ids: list[str] | None = None,
) -> list[str]:
    allowed = {item.id for item in capabilities}
    seed_ids = raw_ids if raw_ids is not None else (default_ids if default_ids is not None else [])
    normalized: list[str] = []
    for item in seed_ids:
        if isinstance(item, str) and item in allowed and item not in normalized:
            normalized.append(item)
    return normalized


def _default_preset_for_scopes(available_scopes: list[str] | None) -> str:
    scopes = set(available_scopes or [])
    if {
        MCP_CONTENT_WRITE,
        MCP_MODERATION_WRITE,
        MCP_CONFIG_WRITE,
        MCP_ASSETS_WRITE,
    }.issubset(scopes):
        return "full_management"
    if {MCP_CONTENT_WRITE, MCP_MODERATION_WRITE}.issubset(scopes):
        return "basic_management"
    return DEFAULT_MCP_PRESET


def _resolve_selected_preset(
    raw_selected_preset: object,
    presets: list[McpPresetRead],
    available_scopes: list[str] | None,
) -> str:
    preset_map = _preset_map(presets)
    key = str(raw_selected_preset or "").strip()
    if key in preset_map:
        return key
    return _default_preset_for_scopes(available_scopes)


def _scope_preset(scopes: set[str]) -> str:
    readonly = {
        MCP_CONNECT,
        MCP_CONTENT_READ,
        MCP_MODERATION_READ,
        MCP_CONFIG_READ,
        MCP_ASSETS_READ,
    }
    basic = readonly | {MCP_CONTENT_WRITE, MCP_MODERATION_WRITE}
    full = basic | {MCP_CONFIG_WRITE, MCP_ASSETS_WRITE}
    if scopes == full:
        return "full_management"
    if scopes == basic:
        return "basic_management"
    if scopes == readonly:
        return DEFAULT_MCP_PRESET
    return CUSTOM_MCP_PRESET


def resolve_mcp_config(
    session: Session,
    capabilities: list[AgentUsageCapabilityRead],
    *,
    api_key: ApiKey | None = None,
    available_scopes: list[str] | None = None,
) -> McpResolvedConfig:
    _profile, feature_flags = _read_site_feature_flags(session)
    scoped_scopes = list(api_key.scopes or []) if api_key is not None else list(available_scopes or [])
    scoped_capabilities = filter_capabilities_for_scopes(capabilities, scoped_scopes)
    presets = build_mcp_presets(scoped_capabilities)
    selected_preset = _scope_preset(set(scoped_scopes))
    preset_map = _preset_map(presets)
    enabled_capability_ids = [item.id for item in scoped_capabilities]
    is_customized = selected_preset == CUSTOM_MCP_PRESET or (
        set(enabled_capability_ids) != set(preset_map[selected_preset].capability_ids)
    )
    return McpResolvedConfig(
        public_access=bool(feature_flags.get("mcp_public_access", False)),
        enabled_capability_ids=enabled_capability_ids,
        selected_preset=selected_preset,
        is_customized=is_customized,
        presets=presets,
    )


def update_mcp_flags(
    session: Session,
    *,
    public_access: bool | None,
    selected_preset: str | None,
    enabled_capability_ids: list[str] | None,
    capabilities: list[AgentUsageCapabilityRead],
    api_key: ApiKey | None = None,
) -> McpResolvedConfig:
    if selected_preset is not None or enabled_capability_ids is not None:
        raise ValidationError("API key MCP config has been removed; update API key scopes instead")

    profile, feature_flags = _read_site_feature_flags(session)
    current = resolve_mcp_config(
        session,
        capabilities,
        api_key=api_key,
        available_scopes=list(api_key.scopes or []) if api_key is not None else None,
    )

    next_public_access = current.public_access if public_access is None else bool(public_access)

    feature_flags["mcp_public_access"] = next_public_access
    profile.feature_flags = feature_flags

    session.commit()
    session.refresh(profile)

    return resolve_mcp_config(
        session,
        capabilities,
        api_key=api_key,
        available_scopes=list(api_key.scopes or []) if api_key is not None else None,
    )


def mcp_capability_error_payload(kind: str, name: str) -> dict[str, object]:
    return {
        "error": "capability_disabled",
        "capability": build_capability_id(kind, name),
        "message": "This MCP capability is disabled for the current API key.",
    }

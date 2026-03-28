from __future__ import annotations

from typing import Any

import yaml

from aerisun.agent_skillmaps import SKILLMAPS_DIR
from aerisun.api.admin.scopes import MCP_CONNECT
from aerisun.domain.agent.mcp_introspection import list_registered_mcp_capabilities
from aerisun.domain.agent.schemas import AgentSkillMapRead, AgentUsageCapabilityRead, AgentUsageMcpRead, AgentUsageRead


def _normalize_base_url(site_url: str) -> str:
    return (site_url or "").rstrip("/")


def _absolute_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not base_url:
        return path
    return f"{base_url}{path if path.startswith('/') else '/' + path}"


def _visible_capabilities(
    available_scopes: list[str],
) -> tuple[list[AgentUsageCapabilityRead], list[AgentUsageCapabilityRead]]:
    scope_set = set(available_scopes)
    all_caps = list_registered_mcp_capabilities()
    visible = [cap for cap in all_caps if all(scope in scope_set for scope in (cap.required_scopes or []))]
    tools = [item for item in visible if item.kind == "tool"]
    resources = [item for item in visible if item.kind == "resource"]
    return tools, resources


def load_agent_skill_maps(base_url: str = "") -> list[AgentSkillMapRead]:
    items: list[AgentSkillMapRead] = []
    if not SKILLMAPS_DIR.exists():
        return items

    for path in sorted(SKILLMAPS_DIR.glob("*.y*ml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        docs_url = str(data.get("docs_url") or "/api/agent/usage")
        where = dict(data.get("where") or {})
        endpoint = where.get("endpoint")
        if isinstance(endpoint, str):
            where["endpoint"] = _absolute_url(base_url, endpoint)
        items.append(
            AgentSkillMapRead(
                id=str(data.get("id") or path.stem),
                name=str(data.get("name") or path.stem),
                description=str(data.get("description") or ""),
                version=int(data.get("version") or 1),
                when=dict(data.get("when") or {}),
                where=where,
                docs_url=_absolute_url(base_url, docs_url),
                use_cases=list(data.get("use_cases") or []),
                workflow=dict(data.get("workflow") or {}),
            )
        )
    return items


def build_agent_usage(site_url: str, available_scopes: list[str]) -> AgentUsageRead:
    base_url = _normalize_base_url(site_url)
    tools, resources = _visible_capabilities(available_scopes)
    # Recommend the minimal set to connect + read content + read config.
    # (These are validated when creating API keys.)
    recommended_scopes = [
        MCP_CONNECT,
        "mcp:content:read",
        "mcp:config:read",
    ]

    return AgentUsageRead(
        name="Aerisun Agent Usage",
        auth={"type": "bearer", "header": "Authorization", "format": "Bearer <API_KEY>"},
        endpoint_base=base_url,
        docs_url=_absolute_url(base_url, "/api/agent/usage"),
        recommended_scopes=recommended_scopes,
        mcp=AgentUsageMcpRead(
            endpoint=_absolute_url(base_url, "/api/mcp"),
            transport="streamable-http",
            required_scopes=[MCP_CONNECT],
            available_scopes=list(available_scopes),
            tools=tools,
            resources=resources,
        ),
        skill_maps=load_agent_skill_maps(base_url),
        workflows=[],
    )

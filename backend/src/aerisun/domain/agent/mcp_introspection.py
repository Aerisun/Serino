from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from aerisun.domain.agent.schemas import AgentUsageCapabilityRead
from aerisun.mcp_server import build_mcp


def _coerce_description(obj: Any) -> str:
    """Best-effort pull of a human-readable description from FastMCP registry entries."""
    for attr in ("description", "doc", "__doc__"):
        value = getattr(obj, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _iter_registry_items(registry: Any) -> Iterable[tuple[str, Any]]:
    """Support common registry shapes: dict-like or list-like."""
    if registry is None:
        return []
    if isinstance(registry, dict):
        return list(registry.items())
    if isinstance(registry, (list, tuple)):
        out: list[tuple[str, Any]] = []
        for item in registry:
            name = getattr(item, "name", None)
            if isinstance(name, str) and name:
                out.append((name, item))
        return out
    # Unknown shape
    return []


def _extract_tools(mcp: Any) -> list[McpCapabilityMeta]:
    # FastMCP doesn't guarantee a public introspection API across versions.
    # We try a few stable attribute names and normalize.
    registries = [
        getattr(mcp, "tools", None),
        getattr(mcp, "_tools", None),
        getattr(mcp, "tool_registry", None),
    ]
    tools: list[McpCapabilityMeta] = []
    for reg in registries:
        items = _iter_registry_items(reg)
        if items:
            for name, obj in items:
                policy = _POLICY_META.get(("tool", name), {})
                tools.append(
                    McpCapabilityMeta(
                        name=name,
                        kind="tool",
                        description=_coerce_description(obj) or policy.get("description") or "",
                        required_scopes=list(policy.get("required_scopes") or []),
                        invocation={"transport": "mcp", "tool": name},
                        examples=list(policy.get("examples") or []),
                    )
                )
            break
    return tools


def _extract_resources(mcp: Any) -> list[McpCapabilityMeta]:
    registries = [
        getattr(mcp, "resources", None),
        getattr(mcp, "_resources", None),
        getattr(mcp, "resource_registry", None),
    ]
    resources: list[McpCapabilityMeta] = []
    for reg in registries:
        items = _iter_registry_items(reg)
        if items:
            for uri, obj in items:
                name = str(uri)
                policy = _POLICY_META.get(("resource", name), {})
                resources.append(
                    McpCapabilityMeta(
                        name=name,
                        kind="resource",
                        description=_coerce_description(obj) or policy.get("description") or "",
                        required_scopes=list(policy.get("required_scopes") or []),
                        invocation={"transport": "mcp", "resource": name},
                        examples=list(policy.get("examples") or []),
                    )
                )
            break
    return resources


def list_registered_mcp_capabilities() -> list[AgentUsageCapabilityRead]:
    """Return MCP tools/resources currently registered via build_mcp().

    This is used by both /api/mcp-meta and /api/agent/usage, to avoid drift.
    """

    mcp = build_mcp()

    direct = getattr(mcp, "_aerisun_capabilities", None)
    if direct:
        return [AgentUsageCapabilityRead.model_validate(item) for item in direct]

    items = [*(_extract_tools(mcp)), *(_extract_resources(mcp))]
    return [
        AgentUsageCapabilityRead(
            name=item.name,
            kind=item.kind,
            description=item.description,
            required_scopes=item.required_scopes,
            invocation=item.invocation,
            examples=item.examples,
        )
        for item in items
    ]

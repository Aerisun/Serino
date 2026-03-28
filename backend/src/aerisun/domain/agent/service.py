from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

import yaml
from sqlalchemy.orm import Session

from aerisun.agent_skillmaps import SKILLMAPS_DIR
from aerisun.api.admin.scopes import MCP_CONNECT, MCP_CONTENT_READ, MCP_CONTENT_WRITE
from aerisun.domain.agent.mcp_introspection import list_registered_mcp_capabilities
from aerisun.domain.agent.mcp_settings import (
    filter_capabilities_for_scopes,
    resolve_mcp_config,
    update_mcp_flags,
)
from aerisun.domain.agent.schemas import (
    AgentUsageAuthRead,
    AgentSkillMapRead,
    AgentUsageCapabilityRead,
    AgentUsageEndpointRead,
    AgentUsageMcpTemplateRead,
    AgentUsageMcpRead,
    AgentUsagePlaybookRead,
    AgentUsagePlaybookStepRead,
    AgentUsageQuickstartRead,
    AgentUsageQuickstartStepRead,
    AgentUsageRead,
    AgentUsageScopeGuideRead,
    AgentUsageTroubleshootingRead,
    McpAdminConfigRead,
    McpAdminConfigUpdate,
    McpCapabilityConfigRead,
)
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.iam.models import ApiKey


def _normalize_base_url(site_url: str) -> str:
    return (site_url or "").rstrip("/")


def _absolute_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not base_url:
        return path
    return f"{base_url}{path if path.startswith('/') else '/' + path}"


def _build_usage_endpoints(base_url: str) -> list[AgentUsageEndpointRead]:
    return [
        AgentUsageEndpointRead(
            id="usage_document",
            url=_absolute_url(base_url, "/api/agent/usage"),
            method="GET",
            description="Machine-readable usage and execution guidance",
            required_headers=["Authorization: Bearer <API_KEY>"],
            expected_status=[200],
        ),
        AgentUsageEndpointRead(
            id="mcp_streamable_http",
            url=_absolute_url(base_url, "/api/mcp/mcp"),
            method="POST",
            description="Primary MCP streamable-http endpoint",
            required_headers=["Authorization: Bearer <API_KEY>", "Content-Type: application/json"],
            expected_status=[200, 202],
        ),
        AgentUsageEndpointRead(
            id="mcp_meta",
            url=_absolute_url(base_url, "/api/mcp-meta"),
            method="GET",
            description="Quick capability overview for the current API key",
            required_headers=["Authorization: Bearer <API_KEY>"],
            expected_status=[200],
        ),
        AgentUsageEndpointRead(
            id="mcp_health",
            url=_absolute_url(base_url, "/api/mcp-healthz"),
            method="GET",
            description="MCP access and health check",
            required_headers=["Authorization: Bearer <API_KEY>"],
            expected_status=[200],
        ),
    ]


def _build_quickstart(base_url: str) -> AgentUsageQuickstartRead:
    usage_url = _absolute_url(base_url, "/api/agent/usage")
    mcp_url = _absolute_url(base_url, "/api/mcp/mcp")
    return AgentUsageQuickstartRead(
        summary="Validate auth, confirm capabilities, and execute one safe MCP read call.",
        environment={
            "BASE": base_url or "http://localhost:8000",
            "KEY": "<API_KEY>",
            "MCP_ENDPOINT": mcp_url,
        },
        steps=[
            AgentUsageQuickstartStepRead(
                order=1,
                title="Read usage document",
                goal="Confirm endpoint and scope context for this API key",
                command=(
                    'curl -sS -H "Authorization: Bearer $KEY" '
                    f'"{usage_url}"'
                ),
                expected_result="HTTP 200 with schema_version and mcp.tool/resource lists",
            ),
            AgentUsageQuickstartStepRead(
                order=2,
                title="Check MCP metadata",
                goal="Ensure MCP public access and key permissions are active",
                command=(
                    'curl -sS -H "Authorization: Bearer $KEY" '
                    f'"{_absolute_url(base_url, "/api/mcp-meta")}"'
                ),
                expected_result="HTTP 200 with tools/resources arrays",
            ),
            AgentUsageQuickstartStepRead(
                order=3,
                title="Run first read call",
                goal="Call one safe read-only tool over MCP",
                command=(
                    "Initialize MCP client session, call tools/list, then call "
                    "list_diary_entries(limit=1, offset=0) against $MCP_ENDPOINT"
                ),
                expected_result="MCP call succeeds with isError=false",
            ),
        ],
    )


def _playbook_step(order: int, title: str, action_type: str, payload: dict[str, object], success: str) -> AgentUsagePlaybookStepRead:
    return AgentUsagePlaybookStepRead(
        order=order,
        title=title,
        action_type=action_type,
        payload=payload,
        success_criteria=success,
    )


def _build_playbooks(base_url: str, tool_names: set[str]) -> list[AgentUsagePlaybookRead]:
    list_available = "list_admin_content" in tool_names
    delete_available = "delete_admin_content" in tool_names
    archive_available = "update_admin_content" in tool_names

    return [
        AgentUsagePlaybookRead(
            id="list-content",
            title="List content candidates",
            description="List recent admin content to select target IDs for further actions.",
            available=list_available,
            risk_level="low",
            required_scopes=[MCP_CONNECT, MCP_CONTENT_READ],
            steps=[
                _playbook_step(
                    1,
                    "MCP list call",
                    "mcp_call",
                    {
                        "tool": "list_admin_content",
                        "arguments": {
                            "content_type": "posts",
                            "page": 1,
                            "page_size": 20,
                            "sort_by": "created_at",
                            "sort_order": "desc",
                        },
                    },
                    "Response includes items[].id/title/status",
                ),
                _playbook_step(
                    2,
                    "REST fallback",
                    "curl",
                    {
                        "command": (
                            'curl -sS -H "Authorization: Bearer $KEY" '
                            f'"{_absolute_url(base_url, "/api/v1/admin/posts/?page=1&page_size=20&sort_by=created_at&sort_order=desc")}"'
                        )
                    },
                    "HTTP 200 with paginated items",
                ),
            ],
            verification=[
                "At least one item has id/title/status fields.",
                "Selected IDs are copied for delete/archive operations.",
            ],
        ),
        AgentUsagePlaybookRead(
            id="delete-content",
            title="Delete one content item",
            description="Delete a selected content item by ID.",
            available=delete_available,
            risk_level="high",
            required_scopes=[MCP_CONNECT, MCP_CONTENT_WRITE],
            steps=[
                _playbook_step(
                    1,
                    "MCP delete call",
                    "mcp_call",
                    {
                        "tool": "delete_admin_content",
                        "arguments": {"content_type": "posts", "item_id": "<DELETE_ID>"},
                    },
                    "Call succeeds with isError=false",
                ),
                _playbook_step(
                    2,
                    "REST fallback",
                    "curl",
                    {
                        "command": (
                            'curl -sS -X DELETE -H "Authorization: Bearer $KEY" '
                            f'"{_absolute_url(base_url, "/api/v1/admin/posts/")}<DELETE_ID>"'
                        )
                    },
                    "HTTP 204 No Content",
                ),
            ],
            verification=[
                "GET /api/v1/admin/posts/<DELETE_ID> returns 404.",
                "Listing no longer contains deleted ID.",
            ],
        ),
        AgentUsagePlaybookRead(
            id="archive-content",
            title="Archive one content item",
            description="Set a selected content item status to archived.",
            available=archive_available,
            risk_level="medium",
            required_scopes=[MCP_CONNECT, MCP_CONTENT_WRITE],
            steps=[
                _playbook_step(
                    1,
                    "MCP archive call",
                    "mcp_call",
                    {
                        "tool": "update_admin_content",
                        "arguments": {
                            "content_type": "posts",
                            "item_id": "<ARCHIVE_ID>",
                            "payload": {"status": "archived"},
                        },
                    },
                    "Returned item.status is archived",
                ),
                _playbook_step(
                    2,
                    "REST fallback",
                    "curl",
                    {
                        "command": (
                            'curl -sS -X PUT -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" '
                            "-d '{\"status\":\"archived\"}' "
                            f'"{_absolute_url(base_url, "/api/v1/admin/posts/")}<ARCHIVE_ID>"'
                        )
                    },
                    "HTTP 200 with status=archived",
                ),
            ],
            verification=[
                "GET /api/v1/admin/posts/<ARCHIVE_ID> returns status=archived.",
                "Visibility is private when archive policy applies.",
            ],
        ),
    ]


def _build_troubleshooting(missing_scopes: list[str]) -> list[AgentUsageTroubleshootingRead]:
    scope_fix = ["Grant missing scopes to the API key and retry."]
    if missing_scopes:
        scope_fix.insert(0, f"Missing recommended scopes: {', '.join(missing_scopes)}")

    return [
        AgentUsageTroubleshootingRead(
            code="401",
            symptom="Unauthorized or invalid token",
            likely_causes=[
                "Missing Authorization header",
                "Expired or malformed API key",
                "Using admin session token instead of API key",
            ],
            fixes=[
                "Use Authorization: Bearer <API_KEY>.",
                "Regenerate API key if token was exposed or expired.",
            ],
        ),
        AgentUsageTroubleshootingRead(
            code="403",
            symptom="MCP access is disabled or scope denied",
            likely_causes=[
                "mcp_public_access is disabled",
                "API key lacks mcp:connect",
                "Tool requires write scope but key is read-only",
            ],
            fixes=[
                "Enable MCP public access in admin integrations settings.",
                *scope_fix,
            ],
        ),
        AgentUsageTroubleshootingRead(
            code="404",
            symptom="Content item not found",
            likely_causes=[
                "Wrong content_type bucket",
                "ID already deleted",
                "ID copied with truncation",
            ],
            fixes=[
                "List content again and copy exact ID.",
                "Verify content_type is posts/diary/thoughts/excerpts.",
            ],
        ),
        AgentUsageTroubleshootingRead(
            code="500",
            symptom="Internal server error while using MCP",
            likely_causes=[
                "Server not running latest code",
                "MCP session manager lifecycle not initialized",
                "Transient upstream/database failure",
            ],
            fixes=[
                "Restart dev stack and retry.",
                "Check /api/mcp-healthz with the same API key.",
                "Inspect backend logs with request_id for traceback.",
            ],
        ),
    ]


def _build_mcp_templates() -> list[AgentUsageMcpTemplateRead]:
    return [
        AgentUsageMcpTemplateRead(
            id="initialize-list-call",
            description="Minimal session flow for first successful MCP call",
            sequence=[
                {"step": 1, "operation": "initialize", "arguments": {}},
                {"step": 2, "operation": "list_tools", "arguments": {}},
                {
                    "step": 3,
                    "operation": "call_tool",
                    "arguments": {
                        "name": "list_diary_entries",
                        "input": {"limit": 1, "offset": 0},
                    },
                },
            ],
        ),
        AgentUsageMcpTemplateRead(
            id="list-delete-archive",
            description="Content management sequence: list, delete, archive",
            sequence=[
                {
                    "step": 1,
                    "operation": "call_tool",
                    "arguments": {
                        "name": "list_admin_content",
                        "input": {"content_type": "posts", "page": 1, "page_size": 20},
                    },
                },
                {
                    "step": 2,
                    "operation": "call_tool",
                    "arguments": {
                        "name": "delete_admin_content",
                        "input": {"content_type": "posts", "item_id": "<DELETE_ID>"},
                    },
                },
                {
                    "step": 3,
                    "operation": "call_tool",
                    "arguments": {
                        "name": "update_admin_content",
                        "input": {
                            "content_type": "posts",
                            "item_id": "<ARCHIVE_ID>",
                            "payload": {"status": "archived"},
                        },
                    },
                },
            ],
        ),
    ]


@lru_cache(maxsize=8)
def build_workflow_planning_usage_context(site_url: str) -> dict[str, object]:
    base_url = _normalize_base_url(site_url)
    all_capabilities = list_registered_mcp_capabilities()
    tool_names = {item.name for item in all_capabilities if item.kind == "tool"}

    return {
        "endpoints": [
            {
                "id": item.id,
                "method": item.method,
                "url": item.url,
                "description": item.description,
            }
            for item in _build_usage_endpoints(base_url)
        ],
        "playbooks": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "required_scopes": item.required_scopes,
                "steps": [
                    {
                        "order": step.order,
                        "title": step.title,
                        "action_type": step.action_type,
                        "payload": step.payload,
                    }
                    for step in item.steps
                ],
            }
            for item in _build_playbooks(base_url, tool_names)
        ],
        "mcp_templates": [item.model_dump(mode="json") for item in _build_mcp_templates()],
    }


def _visible_capabilities(
    session: Session,
    available_scopes: list[str] | None,
    *,
    api_key: ApiKey | None = None,
) -> tuple[list[AgentUsageCapabilityRead], list[AgentUsageCapabilityRead]]:
    all_caps = list_registered_mcp_capabilities()
    if api_key is None and available_scopes is None:
        visible = all_caps
    else:
        config = resolve_mcp_config(session, all_caps, api_key=api_key, available_scopes=available_scopes)
        enabled_ids = set(config.enabled_capability_ids)
        visible = [cap for cap in all_caps if cap.id in enabled_ids]
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


def build_agent_usage(
    session: Session,
    site_url: str,
    available_scopes: list[str] | None,
    *,
    api_key: ApiKey | None = None,
) -> AgentUsageRead:
    base_url = _normalize_base_url(site_url)
    tools, resources = _visible_capabilities(session, available_scopes, api_key=api_key)
    tool_names = {item.name for item in tools}
    available_scope_list = list(available_scopes) if available_scopes is not None else []
    recommended_scopes = [MCP_CONNECT]
    for cap in [*tools, *resources]:
        for scope in cap.required_scopes or []:
            if scope not in recommended_scopes:
                recommended_scopes.append(scope)

    missing_scopes = [scope for scope in recommended_scopes if scope not in set(available_scope_list)]
    mcp_endpoint = _absolute_url(base_url, "/api/mcp/mcp")

    return AgentUsageRead(
        schema_version="2026-03-usage-v2",
        generated_at=datetime.now(timezone.utc),
        name="Aerisun Agent Usage",
        objective=(
            "Provide executable MCP and REST guidance so an agent can discover capabilities, "
            "read content, delete content, and archive content with minimal trial-and-error."
        ),
        auth=AgentUsageAuthRead(
            type="bearer",
            header="Authorization",
            format="Bearer <API_KEY>",
            example="Authorization: Bearer <API_KEY>",
            notes=[
                "Use API key tokens from admin integrations API keys, not admin session tokens.",
                "Always send the auth header to /api/agent/usage, /api/mcp-meta, and /api/mcp/mcp.",
            ],
        ),
        endpoints=_build_usage_endpoints(base_url),
        scope_guide=AgentUsageScopeGuideRead(
            required_for_connection=[MCP_CONNECT],
            available_on_current_key=available_scope_list,
            recommended_for_full_management=recommended_scopes,
            missing_recommended_scopes=missing_scopes,
        ),
        quickstart=_build_quickstart(base_url),
        playbooks=_build_playbooks(base_url, tool_names),
        mcp=AgentUsageMcpRead(
            endpoint=mcp_endpoint,
            transport="streamable-http",
            required_scopes=[MCP_CONNECT],
            available_scopes=available_scope_list,
            tools=tools,
            resources=resources,
            call_templates=_build_mcp_templates(),
            usage_hints=[
                "Call list_tools once after initialize and cache tool signatures for the session.",
                "Use list_admin_content to collect IDs before destructive actions.",
                "Prefer update_admin_content(status=archived) over delete for reversible workflows.",
            ],
        ),
        troubleshooting=_build_troubleshooting(missing_scopes),
        skill_maps=load_agent_skill_maps(base_url),
    )


def build_mcp_admin_config(session: Session, site_url: str, api_key_id: str | None = None) -> McpAdminConfigRead:
    base_url = _normalize_base_url(site_url)
    all_capabilities = list_registered_mcp_capabilities()
    api_key = session.get(ApiKey, api_key_id) if api_key_id else None
    if api_key_id and api_key is None:
        raise ResourceNotFound("API key not found")

    scoped_capabilities = (
        filter_capabilities_for_scopes(all_capabilities, list(api_key.scopes or []))
        if api_key is not None
        else []
    )
    resolved = resolve_mcp_config(
        session,
        all_capabilities,
        api_key=api_key,
        available_scopes=list(api_key.scopes or []) if api_key is not None else [],
    )
    enabled_ids = set(resolved.enabled_capability_ids)
    recommended_scopes = [MCP_CONNECT]
    for capability in scoped_capabilities:
        if capability.id not in enabled_ids:
            continue
        for scope in capability.required_scopes or []:
            if scope not in recommended_scopes:
                recommended_scopes.append(scope)

    return McpAdminConfigRead(
        api_key_id=api_key.id if api_key is not None else None,
        api_key_name=api_key.key_name if api_key is not None else None,
        api_key_scopes=list(api_key.scopes or []) if api_key is not None else [],
        public_access=resolved.public_access,
        selected_preset=resolved.selected_preset,
        is_customized=resolved.is_customized,
        enabled_capability_count=len(enabled_ids),
        available_capability_count=len(all_capabilities),
        usage_url=_absolute_url(base_url, "/api/agent/usage"),
        endpoint=_absolute_url(base_url, "/api/mcp/mcp"),
        transport="streamable-http",
        required_scopes=[MCP_CONNECT],
        recommended_scopes=recommended_scopes,
        presets=resolved.presets,
        capabilities=[
            McpCapabilityConfigRead(
                id=item.id,
                name=item.name,
                kind=item.kind,
                description=item.description,
                required_scopes=item.required_scopes,
                enabled=item.id in enabled_ids,
            )
            for item in all_capabilities
        ],
    )


def save_mcp_admin_config(
    session: Session,
    site_url: str,
    payload: McpAdminConfigUpdate,
    api_key_id: str | None = None,
) -> McpAdminConfigRead:
    capabilities = list_registered_mcp_capabilities()
    api_key = session.get(ApiKey, api_key_id) if api_key_id else None
    if api_key_id and api_key is None:
        raise ResourceNotFound("API key not found")
    update_mcp_flags(
        session,
        public_access=payload.public_access,
        selected_preset=payload.selected_preset,
        enabled_capability_ids=payload.enabled_capability_ids,
        capabilities=capabilities,
        api_key=api_key,
    )
    return build_mcp_admin_config(session, site_url, api_key_id)

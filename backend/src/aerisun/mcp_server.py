from __future__ import annotations

import inspect
import json
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import structlog
from fastapi.encoders import jsonable_encoder
from mcp import types
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel

from aerisun.core.db import get_session_factory
from aerisun.core.settings import Settings, get_settings
from aerisun.domain.agent.capabilities.registry import (
    AgentCapabilityDefinition,
    list_capability_definitions,
    list_capability_models,
)
from aerisun.domain.agent.mcp_settings import mcp_capability_error_payload
from aerisun.domain.exceptions import DomainError
from aerisun.mcp_auth import AerisunMcpBearerAuth, get_mcp_principal, require_mcp_principal

MCP_PROTOCOL_VERSION = "2026-07-28"
logger = structlog.get_logger("aerisun.mcp")


def _require_capability(capability: AgentCapabilityDefinition) -> None:
    principal = require_mcp_principal()
    if capability.id not in principal.enabled_capability_ids:
        logger.warning(
            "mcp_capability_invocation",
            api_key_id=principal.api_key_id,
            capability_id=capability.id,
            kind=capability.kind,
            risk_level=capability.risk_level,
            duration_ms=0.0,
            outcome="denied",
            denial_reason="capability_disabled",
        )
        payload = mcp_capability_error_payload(capability.kind, capability.name)
        raise MCPError(code=types.INVALID_PARAMS, message=str(payload["message"]), data=payload)

    required = list(capability.required_scopes)
    missing = [scope for scope in required if scope not in principal.scopes]
    if missing:
        logger.warning(
            "mcp_capability_invocation",
            api_key_id=principal.api_key_id,
            capability_id=capability.id,
            kind=capability.kind,
            risk_level=capability.risk_level,
            duration_ms=0.0,
            outcome="denied",
            denial_reason="missing_scopes",
        )
        raise MCPError(
            code=types.INVALID_PARAMS,
            message="The current API key is missing required scopes.",
            data={"error": "missing_scopes", "required": missing},
        )


def _serialize_resource_result(result: Any, capability: AgentCapabilityDefinition) -> str:
    if capability.response_kind == "text":
        return result if isinstance(result, str) else str(result)
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    return json.dumps(jsonable_encoder(result), ensure_ascii=False)


def _serialize_tool_result(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump()
    return jsonable_encoder(result)


def _invocation_log_fields(
    capability: AgentCapabilityDefinition,
    *,
    started_at: float,
    outcome: str,
) -> dict[str, Any]:
    principal = get_mcp_principal()
    return {
        "api_key_id": principal.api_key_id if principal is not None else None,
        "capability_id": capability.id,
        "kind": capability.kind,
        "risk_level": capability.risk_level,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
        "outcome": outcome,
    }


def _execute_capability(
    capability: AgentCapabilityDefinition,
    session_factory,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    serializer: Callable[[Any], Any],
) -> Any:
    started_at = time.perf_counter()
    _require_capability(capability)
    session = None
    error_type = ResourceError if capability.kind == "resource" else ToolError
    generic_message = (
        "MCP resource execution failed." if capability.kind == "resource" else "MCP tool execution failed."
    )
    try:
        session = session_factory()
        result = capability.handler(session, *args, **kwargs)
        serialized = serializer(result)
    except DomainError as exc:
        logger.warning(
            "mcp_capability_invocation",
            **_invocation_log_fields(capability, started_at=started_at, outcome="domain_error"),
        )
        raise error_type(exc.detail or generic_message) from None
    except Exception:
        logger.exception(
            "mcp_capability_invocation",
            **_invocation_log_fields(capability, started_at=started_at, outcome="error"),
        )
        raise error_type(generic_message) from None
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                logger.exception(
                    "mcp_capability_invocation",
                    **_invocation_log_fields(capability, started_at=started_at, outcome="cleanup_error"),
                )

    logger.info(
        "mcp_capability_invocation",
        **_invocation_log_fields(capability, started_at=started_at, outcome="success"),
    )
    return serialized


def _build_wrapper_signature(capability: AgentCapabilityDefinition) -> inspect.Signature:
    handler_signature = inspect.signature(capability.handler)
    try:
        type_hints = inspect.get_annotations(capability.handler, eval_str=True)
    except Exception:
        type_hints = {}

    parameters = [
        parameter.replace(annotation=type_hints.get(parameter.name, parameter.annotation))
        for parameter in handler_signature.parameters.values()
    ]
    if parameters and parameters[0].name == "session":
        parameters = parameters[1:]
    return_annotation: Any = (
        str if capability.kind == "resource" else type_hints.get("return", handler_signature.return_annotation)
    )
    return handler_signature.replace(parameters=parameters, return_annotation=return_annotation)


def _wrapper_name(capability: AgentCapabilityDefinition) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", f"{capability.kind}_{capability.name}").strip("_") or "capability"


def _build_wrapper_annotations(signature: inspect.Signature) -> dict[str, Any]:
    annotations: dict[str, Any] = {}
    for name, parameter in signature.parameters.items():
        annotations[name] = Any if parameter.annotation is inspect._empty else parameter.annotation
    annotations["return"] = Any if signature.return_annotation is inspect._empty else signature.return_annotation
    return annotations


def _append_unique(values: list[str], value: str) -> None:
    item = value.strip()
    if item and item not in values:
        values.append(item)


def _host_pattern(hostname: str) -> str:
    host = hostname.strip()
    if not host:
        return ""
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _add_url_security_values(url: str, *, allowed_hosts: list[str], allowed_origins: list[str]) -> None:
    parsed = urlsplit(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return

    _append_unique(allowed_origins, f"{parsed.scheme}://{parsed.netloc}")

    host_base = _host_pattern(parsed.hostname or "")
    if parsed.netloc:
        _append_unique(allowed_hosts, parsed.netloc)
    if host_base:
        _append_unique(allowed_hosts, host_base)
        _append_unique(allowed_hosts, f"{host_base}:*")
        _append_unique(allowed_origins, f"{parsed.scheme}://{host_base}")
        _append_unique(allowed_origins, f"{parsed.scheme}://{host_base}:*")


def build_mcp_transport_security(settings: Settings | None = None):
    """Allow MCP requests for the configured public site and local dev origins."""

    from mcp.server.transport_security import TransportSecuritySettings

    resolved = settings or get_settings()
    allowed_hosts: list[str] = []
    allowed_origins: list[str] = []

    for origin in (
        "http://127.0.0.1",
        "http://localhost",
        "http://[::1]",
        resolved.site_url,
        *resolved.cors_origins,
    ):
        _add_url_security_values(origin, allowed_hosts=allowed_hosts, allowed_origins=allowed_origins)

    host = _host_pattern(resolved.host)
    if host:
        _append_unique(allowed_hosts, host)
        _append_unique(allowed_hosts, f"{host}:*")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def mcp_streamable_http_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if not base:
        return "/api/mcp/"
    return f"{base}/api/mcp/"


def _build_resource_wrapper(capability: AgentCapabilityDefinition, session_factory):
    def resource_wrapper(*args, **kwargs):
        return _execute_capability(
            capability,
            session_factory,
            args,
            kwargs,
            lambda result: _serialize_resource_result(result, capability),
        )

    resource_wrapper.__name__ = _wrapper_name(capability)
    resource_wrapper.__doc__ = capability.description
    resource_signature = _build_wrapper_signature(capability)
    resource_wrapper.__annotations__ = _build_wrapper_annotations(resource_signature)
    resource_wrapper.__signature__ = resource_signature
    return resource_wrapper


def _build_tool_wrapper(capability: AgentCapabilityDefinition, session_factory):
    def tool_wrapper(*args, **kwargs):
        return _execute_capability(capability, session_factory, args, kwargs, _serialize_tool_result)

    tool_wrapper.__name__ = _wrapper_name(capability)
    tool_wrapper.__doc__ = capability.description
    tool_signature = _build_wrapper_signature(capability)
    tool_wrapper.__annotations__ = _build_wrapper_annotations(tool_signature)
    tool_wrapper.__signature__ = tool_signature
    return tool_wrapper


def _capability_meta(capability: AgentCapabilityDefinition) -> dict[str, Any]:
    return {
        "capability_id": capability.id,
        "domain": capability.domain,
        "risk_level": capability.risk_level,
        "required_scopes": list(capability.required_scopes),
        "intent": capability.intent,
    }


def _tool_annotations(capability: AgentCapabilityDefinition) -> types.ToolAnnotations:
    read_only = capability.intent == "read"
    state_change = not read_only
    destructive = state_change and (
        capability.risk_level in {"high", "critical"} or "delete" in capability.name.lower()
    )
    return types.ToolAnnotations(
        title=capability.resolved_label_en,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=read_only,
        openWorldHint=False,
    )


class AerisunMCPServer(MCPServer):
    def __init__(self, *, settings: Settings, session_factory, capabilities: list[AgentCapabilityDefinition]) -> None:
        self._aerisun_settings = settings
        self._session_factory = session_factory
        self._capability_by_tool = {item.name: item for item in capabilities if item.kind == "tool"}
        self._capability_by_resource = {item.name: item for item in capabilities if item.kind == "resource"}
        super().__init__(
            name="aerisun_mcp",
            title="Aerisun MCP",
            description="A permission-scoped MCP interface for Aerisun.",
            instructions="Use the capabilities authorized for the current API key. Client protocol negotiation is automatic.",
            version="2.0",
        )

    async def list_tools(self) -> list[Any]:
        allowed = require_mcp_principal().enabled_capability_ids
        tools = await super().list_tools()
        return [item for item in tools if self._capability_by_tool[item.name].id in allowed]

    async def list_resources(self) -> list[Any]:
        allowed = require_mcp_principal().enabled_capability_ids
        resources = await super().list_resources()
        return [item for item in resources if self._capability_by_resource[str(item.uri)].id in allowed]

    async def call_tool(self, name: str, arguments: dict[str, Any], context=None):
        capability = self._capability_by_tool.get(name)
        if capability is not None:
            _require_capability(capability)
        return await super().call_tool(name, arguments, context)

    async def read_resource(self, uri: Any, context=None):
        capability = self._capability_by_resource.get(str(uri))
        if capability is not None:
            _require_capability(capability)
        return await super().read_resource(uri, context)

    def streamable_http_app(self, **kwargs: Any):
        kwargs.setdefault("streamable_http_path", "/")
        kwargs.setdefault("json_response", True)
        kwargs.setdefault("stateless_http", True)
        kwargs.setdefault("transport_security", build_mcp_transport_security(self._aerisun_settings))
        kwargs.setdefault("host", self._aerisun_settings.host)
        app = super().streamable_http_app(**kwargs)
        return AerisunMcpBearerAuth(app, self._session_factory)


def build_mcp() -> AerisunMCPServer:
    """Build the modern, stateless Aerisun MCP server and register its capability catalog."""

    settings = get_settings()
    session_factory = get_session_factory()
    capabilities = list(list_capability_definitions())
    mcp = AerisunMCPServer(settings=settings, session_factory=session_factory, capabilities=capabilities)

    for capability in capabilities:
        if capability.kind == "resource":
            mcp.resource(
                capability.name,
                name=capability.name,
                title=capability.resolved_label_en,
                description=capability.description,
                meta=_capability_meta(capability),
            )(_build_resource_wrapper(capability, session_factory))
        else:
            mcp.tool(
                name=capability.name,
                title=capability.resolved_label_en,
                description=capability.description,
                annotations=_tool_annotations(capability),
                meta=_capability_meta(capability),
                structured_output=True,
            )(_build_tool_wrapper(capability, session_factory))

    mcp._aerisun_capabilities = tuple(item.model_dump() for item in list_capability_models())
    return mcp

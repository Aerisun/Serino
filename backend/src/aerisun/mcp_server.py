from __future__ import annotations

import inspect
import json
import re
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import AnyHttpUrl, BaseModel

from aerisun.api.admin.scopes import AGENT_CONNECT
from aerisun.core.db import get_session_factory
from aerisun.domain.agent.capabilities.registry import (
    AgentCapabilityDefinition,
    list_capability_definitions,
    list_capability_models,
)
from aerisun.domain.agent.mcp_settings import mcp_capability_error_payload, resolve_mcp_config
from aerisun.domain.iam.models import ApiKey
from aerisun.mcp_auth import AerisunMcpTokenVerifier


def _request_scopes(ctx) -> list[str]:
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        if token is not None:
            return list(token.scopes or [])
    except Exception:
        pass

    try:
        meta = getattr(getattr(ctx, "request_context", None), "meta", None)
        scopes = getattr(meta, "scopes", None)
        if scopes:
            return list(scopes)
    except Exception:
        pass

    return []


def _request_api_key_id(ctx) -> str | None:
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        client_id = getattr(token, "client_id", None) if token is not None else None
        if isinstance(client_id, str) and client_id:
            return client_id
    except Exception:
        pass

    try:
        meta = getattr(getattr(ctx, "request_context", None), "meta", None)
        client_id = getattr(meta, "client_id", None)
        if isinstance(client_id, str) and client_id:
            return client_id
    except Exception:
        pass

    return None


def _has_scope(ctx, required: list[str]) -> bool:
    scopes = set(_request_scopes(ctx))
    return all(scope in scopes for scope in required)


def _scope_error(required: list[str]) -> str:
    return '{"error":"missing_scopes","required":' + json.dumps(required) + "}"


def _capability_error(kind: str, name: str) -> str:
    return json.dumps(mcp_capability_error_payload(kind, name), ensure_ascii=False)


def _require_scopes(ctx, required: list[str]) -> None:
    if not _has_scope(ctx, required):
        raise PermissionError(f"Missing required scopes: {', '.join(required)}")


def _capability_enabled(session, capability: AgentCapabilityDefinition, ctx) -> bool:
    api_key_id = _request_api_key_id(ctx)
    api_key = session.get(ApiKey, api_key_id) if api_key_id else None
    enabled_ids = set(
        resolve_mcp_config(
            session,
            list_capability_models(),
            api_key=api_key,
            available_scopes=_request_scopes(ctx),
        ).enabled_capability_ids
    )
    return capability.id in enabled_ids


def _resource_guard(session, capability: AgentCapabilityDefinition, ctx) -> str | None:
    if not _capability_enabled(session, capability, ctx):
        return _capability_error("resource", capability.name)
    if not _has_scope(ctx, list(capability.required_scopes)):
        return _scope_error(list(capability.required_scopes))
    return None


def _tool_guard(session, capability: AgentCapabilityDefinition, ctx) -> dict[str, Any] | None:
    if not _capability_enabled(session, capability, ctx):
        return mcp_capability_error_payload("tool", capability.name)
    _require_scopes(ctx, list(capability.required_scopes))
    return None


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


def _build_wrapper_signature(capability: AgentCapabilityDefinition, *, include_ctx: bool) -> inspect.Signature:
    handler_signature = inspect.signature(capability.handler)
    parameters = [parameter.replace(annotation=Any) for parameter in handler_signature.parameters.values()]
    if parameters and parameters[0].name == "session":
        parameters = parameters[1:]
    if include_ctx:
        ctx_param = inspect.Parameter(
            "ctx",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=Any,
        )
        insert_at = len(parameters)
        for index, parameter in enumerate(parameters):
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                insert_at = index
                break
        parameters = [*parameters[:insert_at], ctx_param, *parameters[insert_at:]]
    return_annotation: Any = str if capability.kind == "resource" else dict[str, Any]
    return handler_signature.replace(parameters=parameters, return_annotation=return_annotation)


def _wrapper_name(capability: AgentCapabilityDefinition) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", f"{capability.kind}_{capability.name}").strip("_") or "capability"


def _build_wrapper_annotations(signature: inspect.Signature) -> dict[str, Any]:
    annotations: dict[str, Any] = {}
    for name, parameter in signature.parameters.items():
        annotations[name] = Any if parameter.annotation is inspect._empty else parameter.annotation
    annotations["return"] = Any if signature.return_annotation is inspect._empty else signature.return_annotation
    return annotations


def _build_resource_wrapper(capability: AgentCapabilityDefinition, session_factory):
    def resource_wrapper(*args, **kwargs):
        ctx = kwargs.pop("ctx", None)
        session = session_factory()
        try:
            blocked = _resource_guard(session, capability, ctx)
            if blocked is not None:
                return blocked
            result = capability.handler(session, *args, **kwargs)
            return _serialize_resource_result(result, capability)
        finally:
            session.close()

    resource_wrapper.__name__ = _wrapper_name(capability)
    resource_wrapper.__doc__ = capability.description
    resource_signature = _build_wrapper_signature(capability, include_ctx=False)
    resource_wrapper.__annotations__ = _build_wrapper_annotations(resource_signature)
    # FastMCP validates resource function params strictly against URI template params.
    # Keep context access out of the public signature to avoid mismatch errors.
    resource_wrapper.__signature__ = resource_signature
    return resource_wrapper


def _build_tool_wrapper(capability: AgentCapabilityDefinition, session_factory):
    def tool_wrapper(*args, **kwargs):
        ctx = kwargs.pop("ctx", None)
        session = session_factory()
        try:
            blocked = _tool_guard(session, capability, ctx)
            if blocked is not None:
                return blocked
            result = capability.handler(session, *args, **kwargs)
            return _serialize_tool_result(result)
        finally:
            session.close()

    tool_wrapper.__name__ = _wrapper_name(capability)
    tool_wrapper.__doc__ = capability.description
    # Keep tool signatures free of framework-injected context params,
    # and rely on auth middleware context lookup from request-local state.
    tool_signature = _build_wrapper_signature(capability, include_ctx=False)
    tool_wrapper.__annotations__ = _build_wrapper_annotations(tool_signature)
    tool_wrapper.__signature__ = tool_signature
    return tool_wrapper


def build_mcp():
    """Build an MCP server instance and register Aerisun-managed capabilities."""

    from mcp.server.auth.settings import AuthSettings
    from mcp.server.fastmcp import FastMCP

    session_factory = get_session_factory()
    capabilities = list_capability_definitions()

    mcp = FastMCP(
        "Aerisun",
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        token_verifier=AerisunMcpTokenVerifier(session_factory),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl("https://aerisun.invalid"),
            resource_server_url=AnyHttpUrl("http://localhost"),
            required_scopes=[AGENT_CONNECT],
        ),
    )

    for capability in capabilities:
        if capability.kind == "resource":
            mcp.resource(capability.name)(_build_resource_wrapper(capability, session_factory))
        else:
            mcp.tool(name=capability.name)(_build_tool_wrapper(capability, session_factory))

    mcp._aerisun_capabilities = tuple(item.model_dump() for item in list_capability_models())
    return mcp

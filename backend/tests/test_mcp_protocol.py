from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

import httpx
import pytest
from structlog.testing import capture_logs

import aerisun.mcp_auth as mcp_auth_module
import aerisun.mcp_server as mcp_server_module
from aerisun.api.admin.scopes import AGENT_CONNECT, CONFIG_READ, CONTENT_READ, CONTENT_WRITE
from aerisun.domain.agent.capabilities.registry import list_capability_definitions
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.iam.models import ApiKey
from aerisun.domain.iam.service import create_api_key
from aerisun.domain.site_config import repository as site_repo
from aerisun.mcp_server import build_mcp

MCP_PROTOCOL_VERSION = "2026-07-28"
CODEX_PROTOCOL_VERSION = "2025-06-18"
CLAUDE_CODE_PROTOCOL_VERSION = "2025-11-25"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
MAX_MCP_REQUEST_BODY_SIZE = 4 * 1024 * 1024


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def mcp_keys(seeded_session) -> dict[str, str]:
    profile = site_repo.find_site_profile(seeded_session)
    assert profile is not None
    profile.feature_flags = {**dict(profile.feature_flags or {}), "mcp_public_access": True}

    keys: dict[str, str] = {}
    for name, scopes in (
        ("content-read", [AGENT_CONNECT, CONTENT_READ]),
        ("config-read", [AGENT_CONNECT, CONFIG_READ]),
        ("content-manage", [AGENT_CONNECT, CONTENT_READ, CONTENT_WRITE]),
    ):
        created = create_api_key(seeded_session, f"protocol-{name}", scopes)
        keys[name] = created.raw_key
        keys[f"{name}-id"] = created.item.id

    seeded_session.commit()
    return keys


def _modern_meta(version: str = MCP_PROTOCOL_VERSION) -> dict[str, Any]:
    return {
        PROTOCOL_VERSION_META_KEY: version,
        CLIENT_CAPABILITIES_META_KEY: {},
    }


def _rpc_request(method: str, params: dict[str, Any] | None = None, *, request_id: int = 1) -> dict[str, Any]:
    body_params = dict(params or {})
    body_params.setdefault("_meta", _modern_meta())
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}


def _modern_headers(raw_key: str, method: str, *, name: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def _legacy_headers(raw_key: str, protocol_version: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if protocol_version is not None:
        headers["MCP-Protocol-Version"] = protocol_version
    return headers


@asynccontextmanager
async def _running_mcp_client(*, headers: dict[str, str] | None = None):
    server = build_mcp()
    app = server.streamable_http_app()
    async with (
        server.session_manager.run(),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
            headers=headers,
        ) as client,
    ):
        yield client


async def _post_rpc(
    client: httpx.AsyncClient,
    raw_key: str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    name: str | None = None,
    request_id: int = 1,
) -> httpx.Response:
    return await client.post(
        "/",
        headers=_modern_headers(raw_key, method, name=name),
        json=_rpc_request(method, params, request_id=request_id),
    )


@pytest.mark.anyio
async def test_modern_discover_remains_the_preferred_sessionless_protocol(mcp_keys):
    async with _running_mcp_client() as client:
        response = await _post_rpc(client, mcp_keys["content-read"], "server/discover")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result"]["supportedVersions"] == [MCP_PROTOCOL_VERSION]
    assert payload["result"]["capabilities"]["tools"]["listChanged"] is True
    assert payload["result"]["capabilities"]["resources"]["listChanged"] is True
    assert "mcp-session-id" not in response.headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("client_name", "protocol_version"),
    [
        ("codex", CODEX_PROTOCOL_VERSION),
        ("claude-code", CLAUDE_CODE_PROTOCOL_VERSION),
    ],
)
async def test_current_coding_clients_can_initialize_and_use_the_filtered_catalog(
    mcp_keys,
    client_name,
    protocol_version,
):
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": "current"},
        },
    }
    initialized = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    list_tools = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    async with _running_mcp_client() as client:
        initialize_response = await client.post(
            "/",
            headers=_legacy_headers(mcp_keys["content-read"]),
            json=initialize,
        )
        initialized_response = await client.post(
            "/",
            headers=_legacy_headers(mcp_keys["content-read"], protocol_version),
            json=initialized,
        )
        tools_response = await client.post(
            "/",
            headers=_legacy_headers(mcp_keys["content-read"], protocol_version),
            json=list_tools,
        )

    assert initialize_response.status_code == 200, initialize_response.text
    assert initialize_response.json()["result"]["protocolVersion"] == protocol_version
    assert "mcp-session-id" not in initialize_response.headers
    assert initialized_response.status_code == 202
    assert tools_response.status_code == 200, tools_response.text
    tool_names = {item["name"] for item in tools_response.json()["result"]["tools"]}
    assert "list_posts" in tool_names
    assert "get_site_config" not in tool_names
    assert "mcp-session-id" not in tools_response.headers


@pytest.mark.anyio
async def test_initialize_is_removed_from_the_modern_protocol(mcp_keys):
    params = {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "incorrect-modern-client", "version": "1"},
    }
    async with _running_mcp_client() as client:
        response = await _post_rpc(client, mcp_keys["content-read"], "initialize", params)

    payload = response.json()
    assert payload["error"]["code"] == -32601
    assert "mcp-session-id" not in response.headers


@pytest.mark.anyio
async def test_mcp_entrypoint_requires_post_and_bearer_authentication(mcp_keys):
    method = "server/discover"
    body = _rpc_request(method)
    version_headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "Mcp-Method": method,
    }

    async with _running_mcp_client() as client:
        wrong_method = await client.get(
            "/",
            headers={**version_headers, "Authorization": f"Bearer {mcp_keys['content-read']}"},
        )
        missing = await client.post("/", headers=version_headers, json=body)
        invalid = await client.post("/", headers={**version_headers, "Authorization": "Bearer invalid"}, json=body)

    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "POST"
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"].startswith("Bearer")
    assert invalid.status_code == 401


@pytest.mark.anyio
async def test_authentication_infrastructure_failure_is_sanitized(mcp_keys, monkeypatch):
    raw_token = mcp_keys["content-read"]

    def unavailable(_self, _raw_token):
        raise RuntimeError("database topology secret")

    monkeypatch.setattr(mcp_auth_module.AerisunMcpBearerAuth, "_authenticate", unavailable)
    with capture_logs() as logs:
        async with _running_mcp_client() as client:
            response = await _post_rpc(client, raw_token, "server/discover")

    assert response.status_code == 503
    assert response.json() == {"error": "authentication_unavailable"}
    assert "database topology secret" not in response.text
    assert raw_token not in str(logs)
    assert any(item.get("event") == "mcp_authentication_unavailable" for item in logs)


@pytest.mark.anyio
async def test_transport_rejects_invalid_host_origin_and_oversized_body(mcp_keys):
    raw_key = mcp_keys["content-read"]
    method = "server/discover"
    body = _rpc_request(method)
    headers = _modern_headers(raw_key, method)

    async with _running_mcp_client() as client:
        invalid_host = await client.post("/", headers={**headers, "Host": "attacker.invalid"}, json=body)
        invalid_origin = await client.post(
            "/",
            headers={**headers, "Origin": "https://attacker.invalid"},
            json=body,
        )
        oversized = await client.post(
            "/",
            headers=headers,
            content=b"x" * (MAX_MCP_REQUEST_BODY_SIZE + 1),
        )

    assert invalid_host.status_code == 421
    assert invalid_origin.status_code == 403
    assert oversized.status_code == 413


@pytest.mark.anyio
async def test_disabled_key_and_disabled_mcp_are_rejected(mcp_keys, seeded_session):
    key = seeded_session.get(ApiKey, mcp_keys["content-read-id"])
    assert key is not None
    key.enabled = False
    seeded_session.commit()

    async with _running_mcp_client() as client:
        disabled_key = await _post_rpc(client, mcp_keys["content-read"], "server/discover")

        key.enabled = True
        profile = site_repo.find_site_profile(seeded_session)
        assert profile is not None
        profile.feature_flags = {**dict(profile.feature_flags or {}), "mcp_public_access": False}
        seeded_session.commit()
        disabled_mcp = await _post_rpc(client, mcp_keys["content-read"], "server/discover")

    assert disabled_key.status_code == 403
    assert disabled_key.json() == {"error": "access_denied"}
    assert disabled_mcp.status_code == 403
    assert disabled_mcp.json() == {"error": "access_denied"}


@pytest.mark.anyio
async def test_catalog_is_filtered_to_the_current_api_key(mcp_keys):
    async with _running_mcp_client() as client:
        content_tools = await _post_rpc(client, mcp_keys["content-read"], "tools/list")
        content_resources = await _post_rpc(client, mcp_keys["content-read"], "resources/list")
        config_tools = await _post_rpc(client, mcp_keys["config-read"], "tools/list")
        config_resources = await _post_rpc(client, mcp_keys["config-read"], "resources/list")

    content_tool_names = {item["name"] for item in content_tools.json()["result"]["tools"]}
    content_resource_uris = {item["uri"] for item in content_resources.json()["result"]["resources"]}
    config_tool_names = {item["name"] for item in config_tools.json()["result"]["tools"]}
    config_resource_uris = {item["uri"] for item in config_resources.json()["result"]["resources"]}

    assert "list_posts" in content_tool_names
    assert "get_site_config" not in content_tool_names
    assert "aerisun://posts" in content_resource_uris
    assert "aerisun://site-config" not in content_resource_uris
    assert "get_site_config" in config_tool_names
    assert "list_posts" not in config_tool_names
    assert "aerisun://site-config" in config_resource_uris
    assert "aerisun://posts" not in config_resource_uris


@pytest.mark.anyio
async def test_catalog_and_calls_follow_each_api_keys_explicit_capability_config(mcp_keys, seeded_session):
    content_key = seeded_session.get(ApiKey, mcp_keys["content-read-id"])
    assert content_key is not None
    content_key.mcp_config = {"enabled_capability_ids": ["tool:list_posts", "resource:aerisun://posts"]}
    second = create_api_key(
        seeded_session,
        "protocol-explicit-second",
        [AGENT_CONNECT, CONTENT_READ],
    )
    second_key = seeded_session.get(ApiKey, second.item.id)
    assert second_key is not None
    second_key.mcp_config = {"enabled_capability_ids": ["tool:search_content", "resource:aerisun://diary"]}
    seeded_session.commit()

    async with _running_mcp_client() as client:
        first_tools = await _post_rpc(client, mcp_keys["content-read"], "tools/list")
        first_resources = await _post_rpc(client, mcp_keys["content-read"], "resources/list")
        second_tools = await _post_rpc(client, second.raw_key, "tools/list")
        second_resources = await _post_rpc(client, second.raw_key, "resources/list")
        hidden_call = await _post_rpc(
            client,
            mcp_keys["content-read"],
            "tools/call",
            {"name": "search_content", "arguments": {"query": "hidden", "limit": 1}},
            name="search_content",
        )

    assert {item["name"] for item in first_tools.json()["result"]["tools"]} == {"list_posts"}
    assert {item["uri"] for item in first_resources.json()["result"]["resources"]} == {"aerisun://posts"}
    assert {item["name"] for item in second_tools.json()["result"]["tools"]} == {"search_content"}
    assert {item["uri"] for item in second_resources.json()["result"]["resources"]} == {"aerisun://diary"}
    assert hidden_call.json()["error"]["data"]["capability"] == "tool:search_content"


@pytest.mark.anyio
async def test_tools_expose_annotations_structured_schemas_and_registry_metadata(mcp_keys):
    async with _running_mcp_client() as client:
        response = await _post_rpc(client, mcp_keys["content-manage"], "tools/list")

    tools = {item["name"]: item for item in response.json()["result"]["tools"]}
    read_tool = tools["list_posts"]
    delete_tool = tools["delete_admin_content"]

    assert read_tool["title"] == "List posts"
    assert read_tool["annotations"] == {
        "title": "List posts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert read_tool["_meta"] == {
        "capability_id": "tool:list_posts",
        "domain": "content",
        "risk_level": "low",
        "required_scopes": [CONTENT_READ],
        "intent": "read",
    }
    assert read_tool["inputSchema"]["type"] == "object"
    assert read_tool["outputSchema"]["type"] == "object"
    assert delete_tool["annotations"]["readOnlyHint"] is False
    assert delete_tool["annotations"]["destructiveHint"] is True
    assert delete_tool["annotations"]["idempotentHint"] is False

    capability = next(item for item in list_capability_definitions() if item.name == "delete_admin_content")
    usage = capability.to_usage_model().model_dump()
    assert usage["intent"] == "write"
    assert usage["label_en"] == "Delete content"
    assert usage["domain"] == "content"
    assert usage["risk_level"] == "high"
    assert "approval_policy" not in usage
    assert "requires_approval" not in usage


@pytest.mark.anyio
async def test_resource_read_succeeds_and_unavailable_resource_is_rejected(mcp_keys):
    uri = "aerisun://posts"
    async with _running_mcp_client() as client:
        allowed = await _post_rpc(
            client,
            mcp_keys["content-read"],
            "resources/read",
            {"uri": uri},
            name=uri,
        )
        denied = await _post_rpc(
            client,
            mcp_keys["config-read"],
            "resources/read",
            {"uri": uri},
            name=uri,
        )

    allowed_payload = allowed.json()
    assert allowed.status_code == 200
    assert allowed_payload["result"]["contents"][0]["uri"] == uri
    assert allowed_payload["result"]["contents"][0]["text"]

    denied_payload = denied.json()
    assert denied_payload["error"]["code"] == -32602
    assert denied_payload["error"]["data"]["capability"] == f"resource:{uri}"


@pytest.mark.anyio
async def test_unexpected_tool_error_is_sanitized_and_audited(mcp_keys, monkeypatch):
    secret = "database-password=do-not-expose"

    def explode(session, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        del session, limit, offset
        raise RuntimeError(secret)

    definitions = list(list_capability_definitions())
    target = next(item for item in definitions if item.kind == "tool" and item.name == "list_posts")
    replacement = replace(target, handler=explode)
    monkeypatch.setattr(
        mcp_server_module,
        "list_capability_definitions",
        lambda: tuple(replacement if item.id == target.id else item for item in definitions),
    )

    with capture_logs() as logs:
        async with _running_mcp_client() as client:
            response = await _post_rpc(
                client,
                mcp_keys["content-read"],
                "tools/call",
                {"name": "list_posts", "arguments": {"limit": 1, "offset": 0}},
                name="list_posts",
            )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert secret not in response.text
    assert "MCP tool execution failed." in result["content"][0]["text"]
    failure = next(
        item for item in logs if item.get("event") == "mcp_capability_invocation" and item.get("outcome") == "error"
    )
    assert failure["api_key_id"] == mcp_keys["content-read-id"]
    assert failure["capability_id"] == "tool:list_posts"
    assert failure["kind"] == "tool"
    assert failure["risk_level"] == "low"
    assert failure["duration_ms"] >= 0


@pytest.mark.anyio
async def test_domain_tool_error_can_return_its_safe_detail(mcp_keys, monkeypatch):
    safe_detail = "The requested content filter is invalid."

    def reject(session, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        del session, limit, offset
        raise ValidationError(safe_detail)

    definitions = list(list_capability_definitions())
    target = next(item for item in definitions if item.kind == "tool" and item.name == "list_posts")
    replacement = replace(target, handler=reject)
    monkeypatch.setattr(
        mcp_server_module,
        "list_capability_definitions",
        lambda: tuple(replacement if item.id == target.id else item for item in definitions),
    )

    with capture_logs() as logs:
        async with _running_mcp_client() as client:
            response = await _post_rpc(
                client,
                mcp_keys["content-read"],
                "tools/call",
                {"name": "list_posts", "arguments": {"limit": 1, "offset": 0}},
                name="list_posts",
            )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert safe_detail in result["content"][0]["text"]
    assert any(
        item.get("event") == "mcp_capability_invocation"
        and item.get("capability_id") == "tool:list_posts"
        and item.get("outcome") == "domain_error"
        for item in logs
    )


@pytest.mark.anyio
async def test_real_read_call_succeeds_and_disabled_tool_call_is_rejected(mcp_keys):
    with capture_logs() as logs:
        async with _running_mcp_client() as client:
            read_response = await _post_rpc(
                client,
                mcp_keys["content-read"],
                "tools/call",
                {"name": "list_posts", "arguments": {"limit": 1, "offset": 0}},
                name="list_posts",
            )
            denied_response = await _post_rpc(
                client,
                mcp_keys["content-read"],
                "tools/call",
                {
                    "name": "create_admin_content",
                    "arguments": {
                        "content_type": "posts",
                        "payload": {"title": "Blocked", "body": "Must not be created"},
                    },
                },
                name="create_admin_content",
            )

    read_result = read_response.json()["result"]
    assert read_result["isError"] is False
    assert isinstance(read_result["structuredContent"], dict)

    denied_payload = denied_response.json()
    assert denied_payload["error"]["code"] == -32602
    assert denied_payload["error"]["data"] == {
        "error": "capability_disabled",
        "capability": "tool:create_admin_content",
        "message": "This MCP capability is disabled for the current API key.",
    }

    audit_outcomes = {
        (item.get("capability_id"), item.get("outcome"))
        for item in logs
        if item.get("event") == "mcp_capability_invocation"
    }
    assert ("tool:list_posts", "success") in audit_outcomes
    assert ("tool:create_admin_content", "denied") in audit_outcomes

    key_id = mcp_keys["content-read-id"]
    from aerisun.core.db import get_session_factory
    from aerisun.domain.content.models import PostEntry

    with get_session_factory()() as session:
        assert session.get(ApiKey, key_id) is not None
        assert session.query(PostEntry).filter(PostEntry.title == "Blocked").first() is None

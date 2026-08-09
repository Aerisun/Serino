#!/usr/bin/env python3
"""Smoke-test a running Aerisun MCP endpoint.

Examples:
    uv run --directory backend python ../scripts/mcp-smoke.py \
      --base-url http://127.0.0.1:8000 \
      --api-key "$AERISUN_MCP_API_KEY"

    uv run --directory backend python ../scripts/mcp-smoke.py \
      --usage-url http://127.0.0.1:8000/api/agent/usage \
      --api-key "$AERISUN_MCP_API_KEY" \
      --mode readonly-examples \
      --max-tool-calls 0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client  # noqa: E402

MCP_PROTOCOL_VERSION = "2026-07-28"
SCOPE_RE = re.compile(r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_-]*$")
PLACEHOLDER_RE = re.compile(
    r"^(<.*>|abc-123|content-id|friend-id|id-[0-9]+|api-key-id|revision-id|run-id|workflow-key|[a-z][a-z0-9_-]*-[0-9]+)$"
)


@dataclass
class Outcome:
    name: str
    status: str
    detail: str = ""


def _shorten_text(value: str, limit: int = 220) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _normalize_mcp_url(value: str) -> str:
    normalized = value.rstrip("/")
    return f"{normalized}/" if normalized else normalized


def _fetch_json(url: str, api_key: str) -> dict[str, Any]:
    req = request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {_shorten_text(body)}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER_RE.match(value.strip()))
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    return False


def _example_arguments(capability: dict[str, Any]) -> dict[str, Any] | None:
    examples = capability.get("examples") or []
    for example in examples:
        if example.get("smoke_safe") is False or example.get("requires"):
            continue
        arguments = example.get("arguments")
        if isinstance(arguments, dict) and not _contains_placeholder(arguments):
            return arguments
    if examples:
        return None

    input_schema = capability.get("invocation", {}).get("input_schema", {})
    required = input_schema.get("required") or []
    if not required:
        return {}
    return None


def _is_read_capability(capability: dict[str, Any]) -> bool:
    if capability.get("intent") != "read":
        return False

    scopes = capability.get("required_scopes")
    if not scopes or not isinstance(scopes, list):
        return False
    return all(
        isinstance(scope, str)
        and bool(SCOPE_RE.fullmatch(scope))
        and (scope == "agent:connect" or scope.endswith(":read"))
        for scope in scopes
    )


def _tool_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return _shorten_text(" ".join(parts))


def _resource_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "contents", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return _shorten_text(" ".join(parts))


def _format_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        details = "; ".join(_format_exception(item) for item in exc.exceptions)
        return _shorten_text(f"{exc}: {details}", limit=500)
    return _shorten_text(str(exc), limit=500)


def _usage_endpoint_map(usage: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("id")): str(item.get("url"))
        for item in usage.get("endpoints") or []
        if isinstance(item, dict) and item.get("id") and item.get("url")
    }


def _usage_capabilities(usage: dict[str, Any] | None, kind: str) -> list[dict[str, Any]]:
    if not usage:
        return []
    mcp = usage.get("mcp")
    if not isinstance(mcp, dict):
        return []
    capabilities = mcp.get(kind)
    if not isinstance(capabilities, list):
        return []
    return [item for item in capabilities if isinstance(item, dict)]


def _capability_names(capabilities: list[dict[str, Any]]) -> set[str]:
    return {item["name"] for item in capabilities if isinstance(item.get("name"), str) and item["name"]}


def _select_tool_examples(
    usage: dict[str, Any],
    *,
    max_tool_calls: int,
) -> tuple[list[tuple[str, dict[str, Any]]], list[Outcome]]:
    selected: list[tuple[str, dict[str, Any]]] = []
    skipped: list[Outcome] = []

    for capability in _usage_capabilities(usage, "tools"):
        name = str(capability.get("name") or "")
        if not name:
            continue
        if not _is_read_capability(capability):
            continue

        arguments = _example_arguments(capability)
        if arguments is None:
            skipped.append(Outcome(name, "SKIP", "example requires a real id or required payload"))
            continue

        selected.append((name, arguments))
        if max_tool_calls > 0 and len(selected) >= max_tool_calls:
            break

    return selected, skipped


def _has_trusted_read_examples(usage: dict[str, Any] | None) -> bool:
    if not usage:
        return False
    return any(_is_read_capability(capability) for capability in _usage_capabilities(usage, "tools"))


async def _run_mcp_checks(
    *,
    mcp_url: str,
    api_key: str,
    usage: dict[str, Any] | None,
    mode: str,
    max_tool_calls: int,
) -> list[Outcome]:
    outcomes: list[Outcome] = []
    headers = {"Authorization": f"Bearer {api_key}"}

    async with (
        create_mcp_http_client(headers=headers) as http_client,
        streamable_http_client(mcp_url, http_client=http_client) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        discovery = await session.discover()
        supported_versions = list(discovery.supported_versions)
        discovery_status = "OK" if MCP_PROTOCOL_VERSION in supported_versions else "FAIL"
        outcomes.append(
            Outcome(
                "server/discover",
                discovery_status,
                f"supported_versions={supported_versions}",
            )
        )
        if discovery_status == "FAIL":
            return outcomes

        tools_result = await session.list_tools()
        resources_result = await session.list_resources()
        tool_names = [tool.name for tool in tools_result.tools]
        resource_names = [str(resource.uri) for resource in resources_result.resources]
        outcomes.append(Outcome("tools/list", "OK", f"{len(tool_names)} tools"))
        outcomes.append(Outcome("resources/list", "OK", f"{len(resource_names)} resources"))

        if usage:
            usage_tools = _usage_capabilities(usage, "tools")
            usage_resources = _usage_capabilities(usage, "resources")
            usage_tool_names = _capability_names(usage_tools)
            usage_resource_names = _capability_names(usage_resources)
            protocol_tool_names = set(tool_names)
            protocol_resource_names = set(resource_names)
            missing_tools = sorted(usage_tool_names - protocol_tool_names)
            extra_tools = sorted(protocol_tool_names - usage_tool_names)
            missing_resources = sorted(usage_resource_names - protocol_resource_names)
            extra_resources = sorted(protocol_resource_names - usage_resource_names)
            status = "OK" if not any((missing_tools, extra_tools, missing_resources, extra_resources)) else "FAIL"
            detail = (
                f"missing_tools={missing_tools[:5]} extra_tools={extra_tools[:5]} "
                f"missing_resources={missing_resources[:5]} extra_resources={extra_resources[:5]}"
            )
            outcomes.append(Outcome("usage-vs-mcp", status, detail if status == "FAIL" else "catalogs match"))
            if status == "FAIL":
                return outcomes

        if mode == "discovery" or not _has_trusted_read_examples(usage):
            return outcomes

        trusted_resource_names = {
            item["name"]
            for item in _usage_capabilities(usage, "resources")
            if isinstance(item.get("name"), str) and _is_read_capability(item)
        }
        for uri in resource_names:
            if uri not in trusted_resource_names:
                continue
            try:
                result = await session.read_resource(uri)
                outcomes.append(Outcome(f"resource:{uri}", "OK", _resource_text(result)))
            except Exception as exc:
                outcomes.append(Outcome(f"resource:{uri}", "FAIL", _format_exception(exc)))

        tool_calls, skipped = _select_tool_examples(usage, max_tool_calls=max_tool_calls)
        tool_calls = [(name, args) for name, args in tool_calls if name in tool_names]
        outcomes.extend(skipped)

        for name, arguments in tool_calls:
            try:
                result = await session.call_tool(name, arguments)
                is_error = result.is_error
                outcomes.append(Outcome(f"tool:{name}", "FAIL" if is_error else "OK", _tool_text(result)))
            except Exception as exc:
                outcomes.append(Outcome(f"tool:{name}", "FAIL", _format_exception(exc)))

    return outcomes


def _print_outcomes(outcomes: list[Outcome]) -> None:
    for outcome in outcomes:
        suffix = f" - {outcome.detail}" if outcome.detail else ""
        print(f"[{outcome.status}] {outcome.name}{suffix}")


def _derive_urls(args: argparse.Namespace) -> tuple[str, str, str]:
    base_url = _normalize_base_url(args.base_url or "")
    usage_url = args.usage_url or (f"{base_url}/api/agent/usage" if base_url else "")
    meta_url = args.meta_url or (f"{base_url}/api/mcp-meta" if base_url else "")
    mcp_url = args.url or (f"{base_url}/api/mcp/" if base_url else "")
    if not usage_url and not mcp_url:
        raise SystemExit("Provide --base-url, --usage-url, or --url")
    return usage_url, meta_url, _normalize_mcp_url(mcp_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a running Aerisun MCP endpoint.")
    parser.add_argument("--base-url", help="Aerisun base URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--usage-url", help="Usage document URL. Defaults to <base-url>/api/agent/usage")
    parser.add_argument("--meta-url", help="MCP meta URL. Defaults to <base-url>/api/mcp-meta")
    parser.add_argument("--url", help="Full MCP endpoint URL, e.g. http://127.0.0.1:8000/api/mcp/")
    parser.add_argument("--api-key", required=True, help="Bearer API key used for MCP access")
    parser.add_argument(
        "--mode",
        choices=("discovery", "readonly-examples"),
        default="readonly-examples",
        help="Only inspect discovery/catalogs, or also run usage-declared read-only examples.",
    )
    parser.add_argument(
        "--max-tool-calls",
        type=int,
        default=25,
        help="Maximum example tool calls. Use 0 for no limit.",
    )
    args = parser.parse_args()

    usage_url, meta_url, mcp_url = _derive_urls(args)
    outcomes: list[Outcome] = []
    usage: dict[str, Any] | None = None

    if usage_url:
        try:
            usage = _fetch_json(usage_url, args.api_key)
            endpoint_map = _usage_endpoint_map(usage)
            discovered_mcp_url = (
                args.url or usage.get("mcp", {}).get("endpoint") or endpoint_map.get("mcp_streamable_http") or mcp_url
            )
            mcp_url = _normalize_mcp_url(discovered_mcp_url)
            outcomes.append(Outcome("usage", "OK", f"{len(usage.get('mcp', {}).get('tools', []))} tools"))
        except Exception as exc:
            outcomes.append(Outcome("usage", "FAIL", _format_exception(exc)))

    if meta_url:
        try:
            meta = _fetch_json(meta_url, args.api_key)
            outcomes.append(Outcome("mcp-meta", "OK", f"{len(meta.get('tools', []))} tools"))
        except Exception as exc:
            outcomes.append(Outcome("mcp-meta", "FAIL", _format_exception(exc)))

    health_url = meta_url.replace("/api/mcp-meta", "/api/mcp-healthz") if meta_url else ""
    if health_url:
        try:
            health = _fetch_json(health_url, args.api_key)
            outcomes.append(Outcome("mcp-healthz", "OK", str(health.get("status", "unknown"))))
        except Exception as exc:
            outcomes.append(Outcome("mcp-healthz", "FAIL", _format_exception(exc)))

    try:
        outcomes.extend(
            asyncio.run(
                _run_mcp_checks(
                    mcp_url=mcp_url,
                    api_key=args.api_key,
                    usage=usage,
                    mode=args.mode,
                    max_tool_calls=args.max_tool_calls,
                )
            )
        )
    except Exception as exc:
        outcomes.append(Outcome("mcp-session", "FAIL", _format_exception(exc)))

    _print_outcomes(outcomes)
    failed = [item for item in outcomes if item.status == "FAIL"]
    if failed:
        print(f"Summary: {len(failed)} failed, {len(outcomes) - len(failed)} passed/skipped")
        return 1
    print(f"Summary: all checks passed/skipped ({len(outcomes)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

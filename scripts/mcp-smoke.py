#!/usr/bin/env python3
"""Smoke-test a running Aerisun MCP endpoint.

Usage:
    uv run --directory backend python scripts/mcp-smoke.py \
      --url http://127.0.0.1:8000/api/mcp/ \
      --api-key <API_KEY>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402


def _shorten_text(value: str, limit: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


async def _run_smoke(url: str, api_key: str) -> None:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with streamablehttp_client(url, headers=headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            resources = await session.list_resources()

            print(f"Tool count: {len(tools.tools)}")
            print(f"Resource count: {len(resources.resources)}")
            print("Tool sample:", ", ".join(tool.name for tool in tools.tools[:12]))

            posts = await session.call_tool("list_posts", {"limit": 1, "offset": 0})
            print(f"list_posts isError: {getattr(posts, 'isError', None)}")
            if posts.content:
                print("list_posts sample:", _shorten_text(posts.content[0].text))

            system_info = await session.call_tool("get_system_info", {})
            print(f"get_system_info isError: {getattr(system_info, 'isError', None)}")
            if system_info.content:
                print("get_system_info sample:", _shorten_text(system_info.content[0].text))

            audit_logs = await session.call_tool("list_audit_logs", {"page": 1, "page_size": 1})
            print(f"list_audit_logs isError: {getattr(audit_logs, 'isError', None)}")
            if audit_logs.content:
                print("list_audit_logs sample:", _shorten_text(audit_logs.content[0].text))

            site_config = await session.read_resource("aerisun://site-config")
            if site_config.contents:
                print("site-config sample:", _shorten_text(site_config.contents[0].text))


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a running Aerisun MCP endpoint.")
    parser.add_argument("--url", required=True, help="Full MCP endpoint URL, e.g. http://127.0.0.1:8000/api/mcp/")
    parser.add_argument("--api-key", required=True, help="Bearer API key used for MCP access")
    args = parser.parse_args()
    asyncio.run(_run_smoke(args.url, args.api_key))


if __name__ == "__main__":
    main()

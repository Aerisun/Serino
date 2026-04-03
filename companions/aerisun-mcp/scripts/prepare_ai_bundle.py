#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env"
DEFAULT_OUTPUT_DIR = ROOT / "runtime"
SKILLS_DIR = ROOT / "skills"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def env_value(values: dict[str, str], key: str, default: str = "") -> str:
    return os.getenv(key) or values.get(key, default)


def bool_value(values: dict[str, str], key: str, default: bool) -> bool:
    raw = env_value(values, key, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def list_value(values: dict[str, str], key: str) -> list[str]:
    raw = env_value(values, key, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_url(value: str) -> str:
    return value.rstrip("/")


def resolve_settings(values: dict[str, str]) -> dict[str, Any]:
    base_url = normalize_url(env_value(values, "AERISUN_MCP_BASE_URL"))
    endpoint = normalize_url(env_value(values, "AERISUN_MCP_ENDPOINT"))
    usage_url = normalize_url(env_value(values, "AERISUN_MCP_USAGE_URL"))
    meta_url = normalize_url(env_value(values, "AERISUN_MCP_META_URL"))
    api_key = env_value(values, "AERISUN_MCP_API_KEY")

    if not endpoint:
        if not base_url:
            raise SystemExit("Missing AERISUN_MCP_BASE_URL or AERISUN_MCP_ENDPOINT")
        endpoint = f"{base_url}/api/mcp"

    if not usage_url:
        if not base_url:
            raise SystemExit("Missing AERISUN_MCP_BASE_URL or AERISUN_MCP_USAGE_URL")
        usage_url = f"{base_url}/api/agent/usage"

    if not meta_url:
        if not base_url:
            raise SystemExit("Missing AERISUN_MCP_BASE_URL or AERISUN_MCP_META_URL")
        meta_url = f"{base_url}/api/mcp-meta"

    if not api_key:
        raise SystemExit("Missing AERISUN_MCP_API_KEY in .env")

    return {
        "base_url": base_url,
        "endpoint": endpoint,
        "usage_url": usage_url,
        "meta_url": meta_url,
        "api_key": api_key,
        "require_readonly": bool_value(values, "AERISUN_MCP_REQUIRE_READONLY", True),
        "confirm_before_write": bool_value(values, "AERISUN_MCP_CONFIRM_BEFORE_WRITE", True),
        "allowed_write_tools": list_value(values, "AERISUN_MCP_ALLOWED_WRITE_TOOLS"),
        "allowed_write_resources": list_value(values, "AERISUN_MCP_ALLOWED_WRITE_RESOURCES"),
    }


def fetch_json(url: str, api_key: str) -> dict[str, Any]:
    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} for {url}: {detail}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Failed to reach {url}: {exc.reason}") from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_skill_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
      return {}

    closing = text.find("\n---\n", 4)
    if closing == -1:
      return {}

    frontmatter = text[4:closing]
    result: dict[str, str] = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def build_skill_manifest() -> list[dict[str, Any]]:
    if not SKILLS_DIR.exists():
        return []

    skills: list[dict[str, Any]] = []
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        frontmatter = read_skill_frontmatter(skill_file)
        skill_dir = skill_file.parent
        agent_file = skill_dir / "agents" / "openai.yaml"
        skills.append(
            {
                "name": frontmatter.get("name") or skill_dir.name,
                "description": frontmatter.get("description", ""),
                "skill_path": str(skill_file.relative_to(ROOT)),
                "agent_path": str(agent_file.relative_to(ROOT)) if agent_file.exists() else None,
                "has_agent_config": agent_file.exists(),
            }
        )
    return skills


def is_read_only_tool_name(name: str) -> bool:
    normalized = name.strip().lower()
    prefixes = (
        "get",
        "list",
        "read",
        "search",
        "fetch",
        "inspect",
        "describe",
        "query",
        "preview",
    )
    return normalized.startswith(prefixes)


def build_openai_tool_templates(settings: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    mcp = usage.get("mcp", {})
    discovered_tools = [
        item.get("name", "").strip()
        for item in mcp.get("tools", [])
        if isinstance(item, dict) and item.get("name")
    ]
    read_only_tools = [name for name in discovered_tools if is_read_only_tool_name(name)]
    guarded_write_tools = sorted(set(read_only_tools + settings["allowed_write_tools"]))

    return {
        "readonly": {
            "type": "mcp",
            "server_label": "aerisun-readonly",
            "server_url": settings["endpoint"],
            "require_approval": "never",
            "allowed_tools": read_only_tools,
            "headers": {
                "Authorization": "Bearer ${AERISUN_MCP_API_KEY}",
            },
        },
        "guarded_write": {
            "type": "mcp",
            "server_label": "aerisun-guarded-write",
            "server_url": settings["endpoint"],
            "require_approval": "always" if settings["confirm_before_write"] else "never",
            "allowed_tools": guarded_write_tools,
            "headers": {
                "Authorization": "Bearer ${AERISUN_MCP_API_KEY}",
            },
        },
    }


def build_client_template(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "mcpServers": {
            "aerisun": {
                "transport": "streamable_http",
                "url": "${AERISUN_MCP_ENDPOINT}",
                "headers": {
                    "Authorization": "Bearer ${AERISUN_MCP_API_KEY}",
                },
                "notes": {
                    "usage_url": settings["usage_url"],
                    "meta_url": settings["meta_url"],
                },
            }
        }
    }


def build_companion_manifest(settings: dict[str, Any], usage: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    mcp = usage.get("mcp", {})
    tools = [item.get("name", "") for item in mcp.get("tools", []) if isinstance(item, dict)]
    resources = [item.get("name", "") for item in mcp.get("resources", []) if isinstance(item, dict)]
    prompts = [item.get("name", "") for item in mcp.get("prompts", []) if isinstance(item, dict)]
    return {
        "server": {
            "name": meta.get("name", "aerisun-mcp"),
            "endpoint": settings["endpoint"],
            "transport": "streamable_http",
            "usage_url": settings["usage_url"],
            "meta_url": settings["meta_url"],
        },
        "safety": {
            "require_readonly": settings["require_readonly"],
            "confirm_before_write": settings["confirm_before_write"],
            "allowed_write_tools": settings["allowed_write_tools"],
            "allowed_write_resources": settings["allowed_write_resources"],
        },
        "capabilities": {
            "tool_count": len(tools),
            "resource_count": len(resources),
            "prompt_count": len(prompts),
            "read_only_tool_candidates": [name for name in tools if is_read_only_tool_name(name)],
        },
        "skills": build_skill_manifest(),
    }


def build_briefing(settings: dict[str, Any], usage: dict[str, Any], meta: dict[str, Any]) -> str:
    scopes = usage.get("scope_guide", {}).get("available_on_current_key", [])
    mcp = usage.get("mcp", {})
    tool_names = [item.get("name", "") for item in mcp.get("tools", [])]
    resource_names = [item.get("name", "") for item in mcp.get("resources", [])]
    scope_lines = [f"- `{scope}`" for scope in scopes] or ["- No scopes returned by usage document"]
    tool_lines = [f"- `{name}`" for name in tool_names] or ["- None"]
    resource_lines = [f"- `{name}`" for name in resource_names] or ["- None"]

    lines = [
        "# Aerisun MCP Briefing",
        "",
        "## Connection",
        f"- Endpoint: `{settings['endpoint']}`",
        f"- Usage URL: `{settings['usage_url']}`",
        f"- Meta URL: `{settings['meta_url']}`",
        "",
        "## Recommended client posture",
        "- Use a short descriptive server label for remote MCP clients.",
        "- Prefer an explicit `allowed_tools` list instead of exposing every discovered tool by default.",
        "- Keep read-only and guarded-write configurations separate.",
        "",
        "## Current scopes",
        *scope_lines,
        "",
        "## Local safety policy",
        f"- Read-only mode: `{str(settings['require_readonly']).lower()}`",
        f"- Confirm before write: `{str(settings['confirm_before_write']).lower()}`",
        f"- Allowed write tools: `{', '.join(settings['allowed_write_tools']) or '(none)'}`",
        f"- Allowed write resources: `{', '.join(settings['allowed_write_resources']) or '(none)'}`",
        "",
        "## Available MCP capabilities",
        f"- Tools: `{len(tool_names)}`",
        f"- Resources: `{len(resource_names)}`",
        "",
        "### Tool names",
        *tool_lines,
        "",
        "### Resource names",
        *resource_lines,
        "",
        "## Security rules for the AI",
        "- Never print, echo, or persist the raw API key in chat, logs, or generated config files.",
        "- Always read the latest usage document before calling MCP tools.",
        "- If read-only mode is true, do not execute write, moderation, or state-changing tools even if the API key technically has those scopes.",
        "- If a write is requested, only use tools that appear in both the usage document and the local allowlist.",
        "- Read current state first, then write.",
        "",
        "## MCP meta snapshot",
        f"- Name: `{meta.get('name', 'unknown')}`",
        f"- Transport: `{meta.get('transport', 'unknown')}`",
        f"- Status: `{meta.get('status', 'unknown')}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a safe Aerisun MCP runtime bundle for AI clients.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    env_values = load_env_file(args.env_file)
    settings = resolve_settings(env_values)

    usage = fetch_json(settings["usage_url"], settings["api_key"])
    meta = fetch_json(settings["meta_url"], settings["api_key"])
    openai_templates = build_openai_tool_templates(settings, usage)
    companion_manifest = build_companion_manifest(settings, usage, meta)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_json(args.output_dir / "usage.json", usage)
    write_json(args.output_dir / "mcp-meta.json", meta)
    write_json(args.output_dir / "mcp-client.template.json", build_client_template(settings))
    write_json(args.output_dir / "openai.responses-mcp-tools.template.json", openai_templates)
    write_json(args.output_dir / "companion-manifest.json", companion_manifest)
    (args.output_dir / "briefing.md").write_text(
        build_briefing(settings, usage, meta),
        encoding="utf-8",
    )

    print(f"Wrote {args.output_dir / 'usage.json'}")
    print(f"Wrote {args.output_dir / 'mcp-meta.json'}")
    print(f"Wrote {args.output_dir / 'mcp-client.template.json'}")
    print(f"Wrote {args.output_dir / 'openai.responses-mcp-tools.template.json'}")
    print(f"Wrote {args.output_dir / 'companion-manifest.json'}")
    print(f"Wrote {args.output_dir / 'briefing.md'}")
    print("Secrets were kept in .env only; generated files do not contain the raw API key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

---
name: aerisun-mcp-readonly
description: Use this skill when an AI should read, search, inspect, summarize, or analyze Aerisun data over MCP without changing state. It is the default skill for safe MCP usage.
---

# Aerisun MCP Readonly

This skill is for safe read-first MCP work.

## Preconditions

- Bootstrap access first with `$aerisun-mcp-bootstrap`, or confirm `companions/aerisun-mcp/runtime/usage.json` is fresh enough for the task.
- Respect `companions/aerisun-mcp/.env` local policy, especially `AERISUN_MCP_REQUIRE_READONLY`.

## Rules

- Only use read-only tools and resources.
- Do not call create, update, delete, publish, moderation-write, or config-write style tools.
- Re-check the current usage document before assuming a tool exists.
- Prefer the minimum data needed for the user request.

## Good use cases

- Search posts, diary entries, thoughts, or excerpts
- Read config for diagnosis without changing it
- Summarize, compare, classify, or explain MCP-available data
- Inspect moderation queues without taking moderation actions

## Safety

- If a user asks for a write, hand off to `$aerisun-mcp-guarded-write`.
- Never expose the raw API key.

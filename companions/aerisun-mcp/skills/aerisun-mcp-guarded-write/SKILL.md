---
name: aerisun-mcp-guarded-write
description: Use this skill only when a human explicitly asks the AI to perform a state-changing action through Aerisun MCP, such as writing content, changing config, moderating items, or mutating assets.
---

# Aerisun MCP Guarded Write

This skill is for explicit, controlled MCP mutations.

## Preconditions

- The user must explicitly request a state change.
- Bootstrap access first with `$aerisun-mcp-bootstrap`.
- Read `companions/aerisun-mcp/runtime/briefing.md` before calling write tools.

## Hard rules

- If `AERISUN_MCP_REQUIRE_READONLY=true`, do not execute writes.
- Only use write tools listed in `AERISUN_MCP_ALLOWED_WRITE_TOOLS`.
- Only use write resources listed in `AERISUN_MCP_ALLOWED_WRITE_RESOURCES`.
- If the requested write tool is not both allowlisted and present in the usage document, stop.
- Read current state first, then write.

## Confirmation policy

- If `AERISUN_MCP_CONFIRM_BEFORE_WRITE=true`, require a clear human go-ahead before destructive or surprising writes.
- Always summarize the intended mutation before executing it when there is hidden risk.

## Safety

- Never print or persist the raw API key.
- Avoid broad or batch writes when a narrow write can satisfy the task.
- Prefer auditable, reversible, and minimally scoped changes.

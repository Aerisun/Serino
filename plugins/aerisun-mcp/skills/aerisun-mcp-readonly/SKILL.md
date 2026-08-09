---
name: aerisun-mcp-readonly
description: Use when reading, searching, inspecting, summarizing, comparing, or analyzing data from an installed Aerisun MCP server without changing state.
---

# Aerisun MCP Readonly

Use the smallest currently available read surface that can answer the request.

## Preconditions

- Use the installed MCP server named `aerisun-mcp`.
- Bootstrap first when the current catalog has not been discovered in this task.

## Workflow

1. Select only catalog entries marked read-only by the server, including resources and tools whose metadata identifies a read intent.
2. Request only the fields, records, and time range needed for the user's goal.
3. Summarize the result and distinguish returned facts from your own inference.

## Guardrails

- Do not call create, update, delete, publish, moderation-write, config-write, or other state-changing tools.
- Do not guess tools by name or assume a previously visible capability is still available.
- Never expose the raw API key.
- If the user explicitly requests a change, use the authorized-write skill instead.

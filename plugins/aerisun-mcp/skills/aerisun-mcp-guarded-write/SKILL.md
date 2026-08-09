---
name: aerisun-mcp-guarded-write
description: Use when the user explicitly requests a state-changing action through an installed Aerisun MCP server, such as creating content, updating configuration, moderating an item, or changing an asset.
---

# Aerisun MCP Authorized Write

Carry out exactly the state change the user explicitly requested.

## Preconditions

- The user's current request clearly specifies a state change.
- The installed MCP server named `aerisun-mcp` exposes the required write tool in the current catalog. Server-side API-key scopes and per-key capability configuration are authoritative.

## Workflow

1. Read the current state first when it affects correctness or avoids overwriting newer data.
2. Choose the narrowest available write tool and the smallest valid input.
3. Execute the requested change immediately. The explicit request is authorization for that scoped action; do not ask for a second confirmation.
4. Report the concrete result and any server-returned identifier or failure. Never claim success after an error.

## Guardrails

- Stop if the necessary tool is absent from the current server-filtered catalog.
- Do not widen the target, batch size, or side effects beyond the request.
- Prefer auditable, reversible, idempotent operations when the catalog offers a choice.
- Never print, echo, or persist the raw API key.

---
name: aerisun-mcp-bootstrap
description: Use when connecting to an installed Aerisun MCP server, checking access, discovering the current API key's capabilities, or diagnosing an unavailable Aerisun MCP catalog.
---

# Aerisun MCP Bootstrap

Establish the current Aerisun MCP capability boundary before doing real work.

## Workflow

1. Use the installed MCP server named `aerisun-mcp`. The site installer has already selected its exact domain and persisted the API key in the client's private credential storage.
2. Let the installed client negotiate the MCP protocol automatically. Prefer MCP `2026-07-28`; compatibility with current clients is a transport detail and must not change the available capabilities.
3. Inspect the current tools and resources catalog. Treat that server-filtered catalog as authoritative for this API key and this request.
4. Report authentication, protocol, or availability failures without printing the API key.
5. Choose the readonly or authorized-write skill for the requested work.

## Guardrails

- Never print, echo, persist, or ask the user to paste the raw API key into chat.
- Never infer a capability that is absent from the current catalog.
- Do not perform state-changing operations during bootstrap.
- Re-discover after credentials, scopes, or server configuration change.

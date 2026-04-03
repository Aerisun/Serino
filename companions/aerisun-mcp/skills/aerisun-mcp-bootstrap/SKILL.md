---
name: aerisun-mcp-bootstrap
description: Use this skill when an AI needs to connect to Aerisun MCP, verify the API key, fetch the latest usage document, or prepare safe local MCP client files from the companion bundle.
---

# Aerisun MCP Bootstrap

Use this skill to establish safe Aerisun MCP access before any real work.

## Workflow

1. Ensure `companions/aerisun-mcp/.env` exists.
If it is missing, run `bash companions/aerisun-mcp/scripts/init_env.sh`.

2. Never print the raw API key into chat, logs, or generated files.

3. Run:

```bash
python3 companions/aerisun-mcp/scripts/prepare_ai_bundle.py
```

4. Read these generated files before acting:

- `companions/aerisun-mcp/runtime/briefing.md`
- `companions/aerisun-mcp/runtime/usage.json`
- `companions/aerisun-mcp/runtime/mcp-meta.json`

5. Use the MCP endpoint from `runtime/briefing.md` or `AERISUN_MCP_ENDPOINT`.

## Guardrails

- Treat the usage document as the source of truth for currently available tools and resources.
- If usage or meta fetch fails, stop and report the auth or availability issue.
- Do not perform write operations during bootstrap.

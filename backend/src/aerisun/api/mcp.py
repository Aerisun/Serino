from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import MCP_CONNECT
from aerisun.api.deps.machine_auth import require_api_key_scopes
from aerisun.core.db import get_session
from aerisun.domain.agent.mcp_introspection import list_registered_mcp_capabilities
from aerisun.domain.site_config.service import mcp_public_access_enabled
from aerisun.mcp_server import build_mcp

router = APIRouter(tags=["mcp"], include_in_schema=False)


@router.get("/api/mcp-meta", status_code=status.HTTP_200_OK)
def mcp_root(
    session: Session = Depends(get_session),
    _api_key=Depends(require_api_key_scopes(MCP_CONNECT)),
) -> dict[str, object]:
    if not mcp_public_access_enabled(session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MCP access is disabled")
    visible = [
        cap
        for cap in list_registered_mcp_capabilities()
        if all(scope in (_api_key.scopes or []) for scope in (cap.required_scopes or []))
    ]
    return {
        "name": "Aerisun MCP",
        "transport": "streamable-http",
        "status": "ready",
        "tools": [cap.name for cap in visible if cap.kind == "tool"],
        "resources": [cap.name for cap in visible if cap.kind == "resource"],
    }


@router.get("/api/mcp-healthz", status_code=status.HTTP_200_OK)
def mcp_healthz(
    session: Session = Depends(get_session),
    _api_key=Depends(require_api_key_scopes(MCP_CONNECT)),
) -> dict[str, str]:
    if not mcp_public_access_enabled(session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MCP access is disabled")
    return {"status": "ok"}


mcp_app = build_mcp().streamable_http_app()

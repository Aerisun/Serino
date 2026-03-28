from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import MCP_CONNECT
from aerisun.api.deps.machine_auth import require_api_key_scopes
from aerisun.core.db import get_session
from aerisun.domain.agent.service import build_agent_usage
from aerisun.domain.site_config.service import mcp_public_access_enabled
from aerisun.mcp_server import build_mcp

router = APIRouter(tags=["mcp"], include_in_schema=False)


@router.get("/api/mcp-meta", status_code=status.HTTP_200_OK)
def mcp_root(
    session: Session = Depends(get_session),
    api_key=Depends(require_api_key_scopes(MCP_CONNECT)),
) -> dict[str, object]:
    if not mcp_public_access_enabled(session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MCP access is disabled")
    usage = build_agent_usage(session, "", list(api_key.scopes or []), api_key=api_key)
    return {
        "name": "Aerisun MCP",
        "transport": "streamable-http",
        "status": "ready",
        "tools": [cap.name for cap in usage.mcp.tools],
        "resources": [cap.name for cap in usage.mcp.resources],
    }


@router.get("/api/mcp-healthz", status_code=status.HTTP_200_OK)
def mcp_healthz(
    session: Session = Depends(get_session),
    _api_key=Depends(require_api_key_scopes(MCP_CONNECT)),
) -> dict[str, str]:
    if not mcp_public_access_enabled(session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MCP access is disabled")
    return {"status": "ok"}


@asynccontextmanager
async def _noop_lifespan(_app):
    # MCP session manager lifecycle is handled by the main FastAPI app lifespan.
    yield


def create_mcp_mount():
    """Create a fresh MCP server instance and mounted app for each FastAPI app."""

    mcp_server = build_mcp()
    mcp_app = mcp_server.streamable_http_app()
    mcp_app.router.lifespan_context = _noop_lifespan
    return mcp_server, mcp_app

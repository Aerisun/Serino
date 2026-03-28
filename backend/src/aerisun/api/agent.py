from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import MCP_CONNECT
from aerisun.api.deps.machine_auth import require_api_key_scopes
from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.agent.schemas import AgentUsageRead
from aerisun.domain.agent.service import build_agent_usage
from aerisun.domain.site_config.service import mcp_public_access_enabled

router = APIRouter(tags=["agent"], include_in_schema=True)


@router.get("/api/agent/usage", response_model=AgentUsageRead, status_code=status.HTTP_200_OK)
def agent_usage(
    session: Session = Depends(get_session),
    api_key=Depends(require_api_key_scopes(MCP_CONNECT)),
) -> AgentUsageRead:
    """Capability discovery endpoint for external agents."""

    if not mcp_public_access_enabled(session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MCP access is disabled")

    settings = get_settings()
    return build_agent_usage(settings.site_url, list(api_key.scopes or []))

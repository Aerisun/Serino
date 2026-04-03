from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aerisun.api.deps.machine_auth import require_mcp_api_access
from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.agent.schemas import AgentUsageRead
from aerisun.domain.agent.service import build_agent_usage

router = APIRouter(tags=["agent"], include_in_schema=True)


@router.get("/api/agent/usage", response_model=AgentUsageRead, status_code=status.HTTP_200_OK)
def agent_usage(
    session: Session = Depends(get_session),
    api_key=Depends(require_mcp_api_access()),
) -> AgentUsageRead:
    """Capability discovery endpoint for external agents."""

    settings = get_settings()
    return build_agent_usage(session, settings.site_url, list(api_key.scopes or []), api_key=api_key)

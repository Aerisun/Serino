from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.exceptions import PermissionDenied
from aerisun.domain.iam.models import ApiKey
from aerisun.domain.iam.service import validate_api_key
from aerisun.domain.site_config.service import mcp_public_access_enabled


def verify_mcp_api_key(session: Session, token: str, scopes: tuple[str, ...]) -> ApiKey:
    if not mcp_public_access_enabled(session):
        raise PermissionDenied("MCP access is disabled")
    return validate_api_key(session, token, scopes)

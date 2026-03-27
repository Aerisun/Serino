from __future__ import annotations

from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import MCP_CONNECT
from aerisun.domain.iam.service import validate_api_key
from aerisun.domain.site_config.service import mcp_public_access_enabled


class AerisunMcpTokenVerifier(TokenVerifier):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def verify_token(self, token: str) -> AccessToken | None:
        session: Session = self._session_factory()
        try:
            if not mcp_public_access_enabled(session):
                return None
            key = validate_api_key(session, token, (MCP_CONNECT,))
            return AccessToken(
                token=token,
                client_id=key.id,
                scopes=list(key.scopes or []),
                expires_at=None,
            )
        except Exception:
            return None
        finally:
            session.close()

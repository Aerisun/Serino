from __future__ import annotations

from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import AGENT_CONNECT
from aerisun.domain.iam.mcp_access import verify_mcp_api_key


class AerisunMcpTokenVerifier(TokenVerifier):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def verify_token(self, token: str) -> AccessToken | None:
        session: Session = self._session_factory()
        try:
            key = verify_mcp_api_key(session, token, (AGENT_CONNECT,))
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

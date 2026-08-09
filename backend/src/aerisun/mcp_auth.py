from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import anyio.to_thread
import structlog
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from aerisun.api.admin.scopes import AGENT_CONNECT
from aerisun.domain.agent.capabilities.registry import list_capability_models
from aerisun.domain.agent.mcp_settings import resolve_mcp_config
from aerisun.domain.exceptions import AuthenticationFailed, PermissionDenied
from aerisun.domain.iam.mcp_access import verify_mcp_api_key

logger = structlog.get_logger("aerisun.mcp.auth")


@dataclass(frozen=True, slots=True)
class McpPrincipal:
    api_key_id: str
    scopes: frozenset[str]
    enabled_capability_ids: frozenset[str]


_current_mcp_principal: ContextVar[McpPrincipal | None] = ContextVar("current_mcp_principal", default=None)


def get_mcp_principal() -> McpPrincipal | None:
    return _current_mcp_principal.get()


def require_mcp_principal() -> McpPrincipal:
    principal = get_mcp_principal()
    if principal is None:
        raise PermissionError("An authenticated MCP principal is required")
    return principal


def _bearer_token(scope: Scope) -> str | None:
    authorization = next(
        (value.decode("latin-1") for name, value in scope.get("headers", []) if name.lower() == b"authorization"),
        None,
    )
    if authorization is None:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        return None
    return parts[1]


class AerisunMcpBearerAuth:
    """Authenticate one stateless MCP request and expose only non-secret principal data."""

    def __init__(self, app: ASGIApp, session_factory) -> None:
        self._app = app
        self._session_factory = session_factory

    def __getattr__(self, name: str) -> Any:
        return getattr(self._app, name)

    def _authenticate(self, raw_token: str) -> McpPrincipal:
        session: Session = self._session_factory()
        try:
            api_key = verify_mcp_api_key(session, raw_token, (AGENT_CONNECT,))
            resolved = resolve_mcp_config(
                session,
                list_capability_models(),
                api_key=api_key,
                available_scopes=list(api_key.scopes or []),
            )
            return McpPrincipal(
                api_key_id=api_key.id,
                scopes=frozenset(api_key.scopes or []),
                enabled_capability_ids=frozenset(resolved.enabled_capability_ids),
            )
        finally:
            session.close()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("method") != "POST":
            await Response(status_code=405, headers={"Allow": "POST"})(scope, receive, send)
            return

        raw_token = _bearer_token(scope)
        if raw_token is None:
            await JSONResponse(
                {"error": "authentication_required"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="aerisun-mcp"'},
            )(scope, receive, send)
            return

        try:
            principal = await anyio.to_thread.run_sync(self._authenticate, raw_token)
        except AuthenticationFailed:
            await JSONResponse(
                {"error": "invalid_credentials"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="aerisun-mcp"'},
            )(scope, receive, send)
            return
        except PermissionDenied:
            await JSONResponse({"error": "access_denied"}, status_code=403)(scope, receive, send)
            return
        except Exception:
            logger.exception("mcp_authentication_unavailable")
            await JSONResponse({"error": "authentication_unavailable"}, status_code=503)(scope, receive, send)
            return

        token = _current_mcp_principal.set(principal)
        try:
            await self._app(scope, receive, send)
        finally:
            _current_mcp_principal.reset(token)

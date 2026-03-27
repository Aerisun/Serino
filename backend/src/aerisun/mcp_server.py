from __future__ import annotations

from functools import lru_cache

from mcp.server.fastmcp import Context
from pydantic import AnyHttpUrl

from aerisun.api.admin.scopes import MCP_CONFIG_READ, MCP_CONNECT, MCP_CONTENT_READ
from aerisun.core.db import get_session_factory
from aerisun.domain.content.feed_service import build_posts_rss_xml
from aerisun.domain.content.search_service import search_public_content
from aerisun.domain.content.service import get_public_post, list_public_posts
from aerisun.domain.site_config.service import get_site_config
from aerisun.mcp_auth import AerisunMcpTokenVerifier


def _request_scopes(ctx) -> list[str]:
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        if token is not None:
            return list(token.scopes or [])
    except Exception:
        pass

    try:
        meta = getattr(getattr(ctx, "request_context", None), "meta", None)
        scopes = getattr(meta, "scopes", None)
        if scopes:
            return list(scopes)
    except Exception:
        pass

    return []


def _has_scope(ctx, required: list[str]) -> bool:
    scopes = set(_request_scopes(ctx))
    return all(s in scopes for s in required)


def _scope_error(required: list[str]) -> str:
    return '{"error":"missing_scopes","required":' + __import__("json").dumps(required) + "}"


def _require_scopes(ctx, required: list[str]) -> None:
    if not _has_scope(ctx, required):
        raise PermissionError(f"Missing required scopes: {', '.join(required)}")


@lru_cache(maxsize=1)
def build_mcp():
    """Build a singleton FastMCP server."""
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.fastmcp import FastMCP

    session_factory = get_session_factory()

    mcp = FastMCP(
        "Aerisun",
        json_response=True,
        stateless_http=True,
        token_verifier=AerisunMcpTokenVerifier(session_factory),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl("https://aerisun.invalid"),
            resource_server_url=AnyHttpUrl("http://localhost"),
            required_scopes=[MCP_CONNECT],
        ),
    )

    @mcp.resource("aerisun://site-config")
    def site_config_resource(ctx: Context) -> str:
        """Return site config as JSON."""
        session = session_factory()
        try:
            if not _has_scope(ctx, [MCP_CONFIG_READ]):
                return _scope_error([MCP_CONFIG_READ])
            return get_site_config(session).model_dump_json()
        finally:
            session.close()

    @mcp.resource("aerisun://posts")
    def posts_resource(ctx: Context) -> str:
        """Return latest posts list as JSON."""
        session = session_factory()
        try:
            if not _has_scope(ctx, [MCP_CONTENT_READ]):
                return _scope_error([MCP_CONTENT_READ])
            return list_public_posts(session, limit=20, offset=0).model_dump_json()
        finally:
            session.close()

    @mcp.resource("aerisun://posts/{slug}")
    def post_resource(slug: str, ctx: Context) -> str:
        """Return a single post by slug as JSON."""
        session = session_factory()
        try:
            if not _has_scope(ctx, [MCP_CONTENT_READ]):
                return _scope_error([MCP_CONTENT_READ])
            return get_public_post(session, slug).model_dump_json()
        finally:
            session.close()

    @mcp.resource("aerisun://feeds/posts")
    def posts_feed_resource(ctx: Context) -> str:
        """Return the posts RSS XML."""
        session = session_factory()
        try:
            if not _has_scope(ctx, [MCP_CONTENT_READ]):
                return _scope_error([MCP_CONTENT_READ])
            return build_posts_rss_xml(session, "http://localhost")
        finally:
            session.close()

    @mcp.tool(name="get_site_config")
    def get_site_config_tool(ctx: Context) -> dict:
        """Get current site config."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONFIG_READ])
            return get_site_config(session).model_dump()
        finally:
            session.close()

    @mcp.tool(name="list_posts")
    def list_posts_tool(limit: int = 20, offset: int = 0, ctx: Context | None = None) -> dict:
        """List published posts."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONTENT_READ])
            return list_public_posts(session, limit=limit, offset=offset).model_dump()
        finally:
            session.close()

    @mcp.tool(name="get_post")
    def get_post_tool(slug: str, ctx: Context) -> dict:
        """Get a published post by slug."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONTENT_READ])
            return get_public_post(session, slug).model_dump()
        finally:
            session.close()

    @mcp.tool(name="search_content")
    def search_content_tool(query: str, limit: int = 10, ctx: Context | None = None) -> dict:
        """Search public content."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONTENT_READ])
            return search_public_content(session, query, limit).model_dump()
        finally:
            session.close()

    return mcp

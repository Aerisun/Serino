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
    """Build a singleton FastMCP server.

    We also attach a normalized Aerisun-owned capability registry onto the FastMCP
    instance (mcp._aerisun_capabilities) so /api/mcp-meta and /api/agent/usage can
    stay consistent without hand-maintained lists.
    """
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.fastmcp import FastMCP

    session_factory = get_session_factory()

    capabilities: list[dict] = []

    def _register_capability(
        *,
        kind: str,
        name: str,
        description: str,
        required_scopes: list[str],
        invocation: dict,
        examples: list[dict] | None = None,
    ) -> None:
        capabilities.append(
            {
                "name": name,
                "kind": kind,
                "description": description,
                "required_scopes": required_scopes,
                "invocation": invocation,
                "examples": examples or [],
            }
        )

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

    _register_capability(
        kind="resource",
        name="aerisun://site-config",
        description="Return site config as JSON.",
        required_scopes=[MCP_CONFIG_READ],
        invocation={"transport": "mcp", "resource": "aerisun://site-config"},
    )

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

    _register_capability(
        kind="resource",
        name="aerisun://posts",
        description="Return latest posts list as JSON.",
        required_scopes=[MCP_CONTENT_READ],
        invocation={"transport": "mcp", "resource": "aerisun://posts"},
    )

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

    _register_capability(
        kind="resource",
        name="aerisun://posts/{slug}",
        description="Return a single post by slug as JSON.",
        required_scopes=[MCP_CONTENT_READ],
        invocation={"transport": "mcp", "resource": "aerisun://posts/{slug}"},
    )

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

    _register_capability(
        kind="resource",
        name="aerisun://feeds/posts",
        description="Return the posts RSS XML.",
        required_scopes=[MCP_CONTENT_READ],
        invocation={"transport": "mcp", "resource": "aerisun://feeds/posts"},
    )

    @mcp.tool(name="get_site_config")
    def get_site_config_tool(ctx: Context) -> dict:
        """Get current site config."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONFIG_READ])
            return get_site_config(session).model_dump()
        finally:
            session.close()

    _register_capability(
        kind="tool",
        name="get_site_config",
        description="Get current site config.",
        required_scopes=[MCP_CONFIG_READ],
        invocation={"transport": "mcp", "tool": "get_site_config"},
        examples=[{"arguments": {}, "scenario": "读取站点基础配置用于判断功能入口。"}],
    )

    @mcp.tool(name="list_posts")
    def list_posts_tool(limit: int = 20, offset: int = 0, ctx: Context | None = None) -> dict:
        """List published posts."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONTENT_READ])
            return list_public_posts(session, limit=limit, offset=offset).model_dump()
        finally:
            session.close()

    _register_capability(
        kind="tool",
        name="list_posts",
        description="List published posts.",
        required_scopes=[MCP_CONTENT_READ],
        invocation={"transport": "mcp", "tool": "list_posts"},
        examples=[{"arguments": {"limit": 10, "offset": 0}, "scenario": "列出最近文章。"}],
    )

    @mcp.tool(name="get_post")
    def get_post_tool(slug: str, ctx: Context) -> dict:
        """Get a published post by slug."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONTENT_READ])
            return get_public_post(session, slug).model_dump()
        finally:
            session.close()

    _register_capability(
        kind="tool",
        name="get_post",
        description="Get a published post by slug.",
        required_scopes=[MCP_CONTENT_READ],
        invocation={"transport": "mcp", "tool": "get_post"},
        examples=[{"arguments": {"slug": "hello-world"}, "scenario": "读取单篇文章正文。"}],
    )

    @mcp.tool(name="search_content")
    def search_content_tool(query: str, limit: int = 10, ctx: Context | None = None) -> dict:
        """Search public content."""
        session = session_factory()
        try:
            _require_scopes(ctx, [MCP_CONTENT_READ])
            return search_public_content(session, query, limit).model_dump()
        finally:
            session.close()

    _register_capability(
        kind="tool",
        name="search_content",
        description="Search public content.",
        required_scopes=[MCP_CONTENT_READ],
        invocation={"transport": "mcp", "tool": "search_content"},
        examples=[{"arguments": {"query": "诗", "limit": 5}, "scenario": "按关键词搜索公开内容。"}],
    )

    setattr(mcp, "_aerisun_capabilities", tuple(capabilities))
    return mcp

"""Application factory — single place for FastAPI assembly."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.staticfiles import StaticFiles

from aerisun.api import api_router
from aerisun.api.exception_handlers import register_exception_handlers
from aerisun.api.mcp import create_mcp_mount
from aerisun.api.seo import router as seo_router
from aerisun.core.bootstrap import lifespan
from aerisun.core.middleware import register_middleware
from aerisun.core.rate_limit import limiter
from aerisun.core.settings import get_settings


def create_app() -> FastAPI:
    """Build and return a fully configured FastAPI application."""
    settings = get_settings()
    mcp_server, mcp_app = create_mcp_mount()

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        async with lifespan(app), mcp_server.session_manager.run():
            yield

    is_prod = settings.environment == "production"
    app = FastAPI(
        title="Aerisun API",
        version="0.1.0",
        lifespan=app_lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Domain exception handlers
    register_exception_handlers(app)

    # Middleware stack
    register_middleware(app, settings)

    # Routers
    app.include_router(api_router)
    app.include_router(seo_router)
    app.include_router(seo_router, prefix="/api/v1/site")

    # MCP Streamable HTTP app (mounted)
    app.mount("/api/mcp", mcp_app)

    # Static media
    media_dir = Path(settings.media_dir).expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    return app

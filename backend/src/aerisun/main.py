from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.staticfiles import StaticFiles

from aerisun.api import api_router
from aerisun.api.exception_handlers import register_exception_handlers
from aerisun.api.seo import router as seo_router
from aerisun.core.logging import setup_logging
from aerisun.core.middleware import register_middleware
from aerisun.core.rate_limit import limiter
from aerisun.core.security import check_insecure_defaults
from aerisun.core.sentry import init_sentry
from aerisun.core.settings import get_settings
from aerisun.core.task_manager import TaskManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    setup_logging(settings)
    check_insecure_defaults(settings)
    init_sentry(settings)

    task_manager = TaskManager(settings)
    await task_manager.start()
    yield
    await task_manager.stop()


app = FastAPI(
    title="Aerisun API",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_exception_handlers(app)
register_middleware(app, _settings)

app.include_router(api_router)
app.include_router(seo_router)

# Serve uploaded media (comment images, etc.) as static files
_media_dir = Path(_settings.media_dir).expanduser().resolve()
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

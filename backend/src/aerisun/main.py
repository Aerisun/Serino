from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from aerisun.api import api_router
from aerisun.api.admin.audit_middleware import AuditLogMiddleware
from aerisun.core.csrf import OriginCheckMiddleware
from aerisun.core.db import run_database_migrations
from aerisun.core.logging import RequestIDMiddleware, setup_logging
from aerisun.core.rate_limit import limiter
from aerisun.core.security_headers import SecurityHeadersMiddleware
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import Settings, get_settings
from aerisun.core.tasks import cleanup_expired_sessions

logger = logging.getLogger("aerisun.startup")


def _check_insecure_defaults(settings: Settings) -> None:
    issues: list[str] = []
    if os.environ.get("WALINE_JWT_TOKEN", "change-me") == "change-me":
        issues.append("WALINE_JWT_TOKEN")
    if settings.has_only_localhost_origins():
        issues.append("CORS origins (only localhost)")
    if not issues:
        return
    msg = f"SECURITY: insecure defaults detected: {', '.join(issues)}. Update them before deploying."
    if settings.environment == "production":
        logger.critical(msg)
        raise SystemExit(msg)
    logger.warning(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    setup_logging(settings)
    _check_insecure_defaults(settings)

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
        )

    run_database_migrations()
    if settings.seed_reference_data:
        seed_reference_data()
    task = asyncio.create_task(cleanup_expired_sessions())

    # Start feed crawler scheduler
    scheduler = None
    if settings.feed_crawl_enabled:
        from apscheduler.schedulers.background import BackgroundScheduler

        from aerisun.domain.social.crawler import crawl_all_feeds

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            crawl_all_feeds,
            trigger="interval",
            hours=settings.feed_crawl_interval_hours,
            id="feed_crawler",
            name="Friend feed crawler",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()

    yield

    task.cancel()
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Aerisun API",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware, settings=_settings)
app.add_middleware(OriginCheckMiddleware, allowed_origins=_settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router)

from aerisun.api.seo import router as seo_router
app.include_router(seo_router)

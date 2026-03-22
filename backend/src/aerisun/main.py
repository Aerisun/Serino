from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aerisun.api import api_router
from aerisun.core.db import run_database_migrations
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import get_settings
from aerisun.core.tasks import cleanup_expired_sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

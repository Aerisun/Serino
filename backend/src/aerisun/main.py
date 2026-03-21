from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from aerisun.api import api_router
from aerisun.db import init_db
from aerisun.seed import seed_reference_data
from aerisun.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    if settings.seed_reference_data:
        seed_reference_data()
    yield


app = FastAPI(
    title="Aerisun API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)


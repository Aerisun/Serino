from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.db import get_session
from aerisun.modules.site_config import get_page_copy, get_resume, get_site_config
from aerisun.schemas import HealthRead, PageCollectionRead, ResumeRead, SiteConfigRead

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/site", response_model=SiteConfigRead)
def read_site_config(session: Session = Depends(get_session)) -> SiteConfigRead:
    return get_site_config(session)


@router.get("/pages", response_model=PageCollectionRead)
def read_page_copy(session: Session = Depends(get_session)) -> PageCollectionRead:
    return get_page_copy(session)


@router.get("/resume", response_model=ResumeRead)
def read_resume(session: Session = Depends(get_session)) -> ResumeRead:
    return get_resume(session)


@router.get("/healthz", response_model=HealthRead)
def healthz() -> HealthRead:
    from aerisun.settings import get_settings

    settings = get_settings()
    return HealthRead(
        status="ok",
        database_path=str(settings.db_path),
        timestamp=datetime.now(timezone.utc),
    )


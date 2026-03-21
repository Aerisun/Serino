from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.infrastructure.database import get_db_session
from aerisun.modules.site_config.schemas import PagesRead, ResumeRead, SiteRead
from aerisun.modules.site_config.service import load_pages_bundle, load_resume_bundle, load_site_bundle

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/site", response_model=SiteRead)
def read_site(session: Session = Depends(get_db_session)) -> SiteRead:
    return load_site_bundle(session)


@router.get("/pages", response_model=PagesRead)
def read_pages(session: Session = Depends(get_db_session)) -> PagesRead:
    return load_pages_bundle(session)


@router.get("/resume", response_model=ResumeRead)
def read_resume(session: Session = Depends(get_db_session)) -> ResumeRead:
    return load_resume_bundle(session)


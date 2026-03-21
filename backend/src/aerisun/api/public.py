from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from aerisun.content import (
    get_public_diary_entry,
    get_public_post,
    list_public_diary_entries,
    list_public_excerpts,
    list_public_posts,
    list_public_thoughts,
)
from aerisun.db import get_session
from aerisun.modules.site_config import get_page_copy, get_resume, get_site_config
from aerisun.schemas import ContentCollectionRead, ContentEntryRead, HealthRead, PageCollectionRead, ResumeRead, SiteConfigRead

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


@router.get("/posts", response_model=ContentCollectionRead)
def read_posts(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_posts(session, limit=limit)


@router.get("/posts/{slug}", response_model=ContentEntryRead)
def read_post(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    try:
        return get_public_post(session, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/diary", response_model=ContentCollectionRead)
def read_diary(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_diary_entries(session, limit=limit)


@router.get("/diary/{slug}", response_model=ContentEntryRead)
def read_diary_entry(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    try:
        return get_public_diary_entry(session, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/thoughts", response_model=ContentCollectionRead)
def read_thoughts(
    limit: int = Query(default=40, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_thoughts(session, limit=limit)


@router.get("/excerpts", response_model=ContentCollectionRead)
def read_excerpts(
    limit: int = Query(default=40, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_excerpts(session, limit=limit)


@router.get("/healthz", response_model=HealthRead)
def healthz() -> HealthRead:
    from aerisun.settings import get_settings

    settings = get_settings()
    return HealthRead(
        status="ok",
        database_path=str(settings.db_path),
        timestamp=datetime.now(timezone.utc),
    )

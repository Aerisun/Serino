from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_SEARCH, limiter
from aerisun.domain.content.schemas import SearchResponse
from aerisun.domain.content.search_service import search_public_content

base_router = APIRouter()
router = APIRouter(prefix="/api/v1/site", tags=["site"])


@base_router.get("/search", response_model=SearchResponse)
@limiter.limit(RATE_SEARCH)
def search_content(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> SearchResponse:
    return search_public_content(session, q, limit)


router.include_router(base_router)

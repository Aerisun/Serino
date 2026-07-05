from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import get_current_site_session_optional, get_current_site_user_optional
from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_SEARCH, limiter
from aerisun.domain.content.schemas import SearchResponse
from aerisun.domain.content.search_service import search_public_content
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession

base_router = APIRouter()
router = APIRouter(prefix="/api/v1/site", tags=["site"])


@base_router.get("/search", response_model=SearchResponse)
@limiter.limit(RATE_SEARCH)
def search_content(
    request: Request,
    response: Response,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> SearchResponse:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"
    return search_public_content(
        session,
        q,
        limit,
        current_user=current_user,
        current_site_session=current_site_session,
    )


router.include_router(base_router)

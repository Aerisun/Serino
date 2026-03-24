from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.schemas import SearchResponse
from aerisun.domain.content.search_service import search_public_content

router = APIRouter(prefix="/api/v1/public", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_content(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> SearchResponse:
    return search_public_content(session, q, limit)

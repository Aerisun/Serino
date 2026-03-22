from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry

router = APIRouter(prefix="/api/v1/public", tags=["search"])

SNIPPET_RADIUS = 120


class SearchResultItem(BaseModel):
    type: str
    slug: str
    title: str
    snippet: str
    published_at: datetime | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int


def _make_snippet(text: str, query: str, radius: int = SNIPPET_RADIUS) -> str:
    if not text:
        return ""
    lower_text = text.lower()
    lower_query = query.lower()
    pos = lower_text.find(lower_query)
    if pos == -1:
        return text[: radius * 2] + ("..." if len(text) > radius * 2 else "")
    start = max(0, pos - radius)
    end = min(len(text), pos + len(query) + radius)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    # Wrap matched text with <mark> tags
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)
    return snippet


@router.get("/search", response_model=SearchResponse)
def search_content(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> SearchResponse:
    pattern = f"%{q}%"
    results: list[SearchResultItem] = []

    content_types = [
        (PostEntry, "posts"),
        (DiaryEntry, "diary"),
        (ThoughtEntry, "thoughts"),
        (ExcerptEntry, "excerpts"),
    ]

    for model, type_name in content_types:
        rows = session.scalars(
            select(model)
            .where(
                model.status == "published",
                model.visibility == "public",
                or_(
                    model.title.ilike(pattern),
                    model.body.ilike(pattern),
                    model.summary.ilike(pattern) if hasattr(model, "summary") else False,
                ),
            )
            .order_by(model.published_at.desc().nullslast())
            .limit(limit)
        ).all()

        for row in rows:
            snippet = _make_snippet(row.body or row.summary or "", q)
            results.append(
                SearchResultItem(
                    type=type_name,
                    slug=row.slug,
                    title=row.title,
                    snippet=snippet,
                    published_at=row.published_at,
                )
            )

    results.sort(key=lambda r: r.published_at or datetime.min, reverse=True)
    results = results[:limit]

    return SearchResponse(items=results, total=len(results))

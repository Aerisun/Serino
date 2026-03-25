from __future__ import annotations

import html
import re
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.schemas import SearchResponse, SearchResultItem

SNIPPET_RADIUS = 120

_CONTENT_TYPES = [
    (PostEntry, "posts"),
    (DiaryEntry, "diary"),
    (ThoughtEntry, "thoughts"),
    (ExcerptEntry, "excerpts"),
]


def _make_snippet(text: str, query: str, radius: int = SNIPPET_RADIUS) -> str:
    if not text:
        return ""
    lower_text = text.lower()
    lower_query = query.lower()
    pos = lower_text.find(lower_query)
    if pos == -1:
        return html.escape(text[: radius * 2]) + ("..." if len(text) > radius * 2 else "")
    start = max(0, pos - radius)
    end = min(len(text), pos + len(query) + radius)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    snippet = html.escape(snippet)
    pattern = re.compile(re.escape(html.escape(query)), re.IGNORECASE)
    snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)
    return snippet


def search_public_content(session: Session, query: str, limit: int = 10) -> SearchResponse:
    pattern = f"%{query}%"
    results: list[SearchResultItem] = []

    for model, type_name in _CONTENT_TYPES:
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
            snippet = _make_snippet(row.body or row.summary or "", query)
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
    return SearchResponse(items=results[:limit], total=len(results[:limit]))

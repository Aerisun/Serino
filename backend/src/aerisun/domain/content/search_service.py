from __future__ import annotations

import html
import re
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.schemas import SearchResponse, SearchResultItem
from aerisun.domain.diary_access.service import diary_private_enabled

SNIPPET_RADIUS = 120

_CONTENT_TYPES = [
    (PostEntry, "posts"),
    (DiaryEntry, "diary"),
    (ThoughtEntry, "thoughts"),
    (ExcerptEntry, "excerpts"),
]


def _split_keywords(query: str) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for keyword in re.split(r"\s+", query.strip()):
        normalized = keyword.casefold()
        if not keyword or normalized in seen:
            continue
        keywords.append(keyword)
        seen.add(normalized)
    return keywords


def _make_snippet(text: str, keywords: list[str], radius: int = SNIPPET_RADIUS) -> str:
    if not text:
        return ""
    if not keywords:
        return html.escape(text[: radius * 2]) + ("..." if len(text) > radius * 2 else "")

    anchor = keywords[0]
    lower_text = text.lower()
    pos = lower_text.find(anchor.lower())
    if pos == -1:
        return html.escape(text[: radius * 2]) + ("..." if len(text) > radius * 2 else "")
    start = max(0, pos - radius)
    end = min(len(text), pos + len(anchor) + radius)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    snippet = html.escape(snippet)

    escaped_keywords = sorted({html.escape(keyword) for keyword in keywords}, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(keyword) for keyword in escaped_keywords), re.IGNORECASE)
    snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)
    return snippet


def _searchable_fields(model) -> tuple:
    fields = [model.title, model.body]
    if hasattr(model, "summary"):
        fields.append(model.summary)
    return tuple(fields)


def _keyword_condition(model, keyword: str):
    pattern = f"%{keyword}%"
    return or_(*(field.ilike(pattern) for field in _searchable_fields(model)))


def _snippet_source(row, first_keyword: str) -> str:
    body = row.body or ""
    summary = row.summary or ""
    first_keyword_lower = first_keyword.lower()
    if first_keyword_lower in body.lower():
        return body
    if first_keyword_lower in summary.lower():
        return summary
    return body or summary


def search_public_content(session: Session, query: str, limit: int = 10) -> SearchResponse:
    keywords = _split_keywords(query)
    if not keywords:
        return SearchResponse(items=[], total=0)

    results: list[SearchResultItem] = []

    include_diary = not diary_private_enabled(session)
    for model, type_name in _CONTENT_TYPES:
        if type_name == "diary" and not include_diary:
            continue
        rows = session.scalars(
            select(model)
            .where(
                model.visibility == "public",
                and_(*(_keyword_condition(model, keyword) for keyword in keywords)),
            )
            .order_by(model.published_at.desc().nullslast())
            .limit(limit)
        ).all()

        for row in rows:
            snippet = _make_snippet(_snippet_source(row, keywords[0]), keywords)
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

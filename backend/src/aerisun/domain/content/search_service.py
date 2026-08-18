from __future__ import annotations

import html
import re
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from aerisun.core.time import shanghai_now
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.schemas import SearchResponse, SearchResultItem
from aerisun.domain.diary_access.service import current_site_user_can_view_diary
from aerisun.domain.post_access.models import PostAccessRequest
from aerisun.domain.post_access.service import post_access_approval_enabled
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.service import is_site_user_admin

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


def search_public_content(
    session: Session,
    query: str,
    limit: int = 10,
    *,
    current_user: SiteUser | None = None,
    current_site_session: SiteUserSession | None = None,
) -> SearchResponse:
    keywords = _split_keywords(query)
    if not keywords:
        return SearchResponse(items=[], total=0)

    results: list[SearchResultItem] = []

    include_diary = current_site_user_can_view_diary(session, current_user, current_site_session)
    hide_protected_posts = post_access_approval_enabled(session)
    for model, type_name in _CONTENT_TYPES:
        if type_name == "diary" and not include_diary:
            continue
        access_conditions = [model.visibility == "public"]
        if model is PostEntry and hide_protected_posts:
            is_admin = current_user is not None and is_site_user_admin(
                session,
                current_user,
                current_site_session,
            )
            if not is_admin and current_user is not None:
                accessible_post_ids = select(PostAccessRequest.post_id).where(
                    PostAccessRequest.site_user_id == current_user.id,
                    PostAccessRequest.status == "approved",
                    PostAccessRequest.revoked_at.is_(None),
                    PostAccessRequest.expires_at.is_not(None),
                    PostAccessRequest.expires_at > shanghai_now(),
                )
                access_conditions.append(
                    or_(
                        PostEntry.requires_approval.is_(False),
                        PostEntry.id.in_(accessible_post_ids),
                    )
                )
            elif not is_admin:
                access_conditions.append(PostEntry.requires_approval.is_(False))
        rows = session.scalars(
            select(model)
            .where(
                *access_conditions,
                and_(*(_keyword_condition(model, keyword) for keyword in keywords)),
            )
            .order_by(model.published_at.desc().nullslast())
            .limit(limit)
        ).all()

        for row in rows:
            snippet = _make_snippet(_snippet_source(row, keywords[0]), keywords)
            result_type = "notes" if model is PostEntry and row.kind == "note" else type_name
            results.append(
                SearchResultItem(
                    type=result_type,
                    slug=row.slug,
                    title=row.title,
                    snippet=snippet,
                    published_at=row.published_at,
                )
            )

    results.sort(key=lambda r: r.published_at or datetime.min, reverse=True)
    return SearchResponse(items=results[:limit], total=len(results[:limit]))

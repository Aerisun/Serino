from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_WRITE_ENGAGEMENT, RATE_WRITE_REACTION, limiter
from aerisun.core.schemas import HealthRead
from aerisun.core.settings import get_settings as _get_settings
from aerisun.domain.activity.schemas import ActivityHeatmapRead, CalendarRead, RecentActivityRead
from aerisun.domain.activity.service import build_activity_heatmap, list_calendar_events, list_recent_activity
from aerisun.domain.content.schemas import ContentCollectionRead, ContentEntryRead
from aerisun.domain.content.service import (
    get_public_diary_entry,
    get_public_post,
    list_public_diary_entries,
    list_public_excerpts,
    list_public_posts,
    list_public_thoughts,
)
from aerisun.domain.engagement.schemas import (
    CommentCollectionRead,
    CommentCreate,
    CommentCreateResponse,
    GuestbookCollectionRead,
    GuestbookCreate,
    GuestbookCreateResponse,
    ReactionCreate,
    ReactionRead,
)
from aerisun.domain.engagement.service import (
    create_public_comment,
    create_public_guestbook_entry,
    list_public_comments,
    list_public_guestbook_entries,
    read_public_reaction,
    register_public_reaction,
)
from aerisun.domain.site_config.schemas import CommunityConfigRead, PageCollectionRead, ResumeRead, SiteConfigRead
from aerisun.domain.site_config.service import get_community_config, get_page_copy, get_resume, get_site_config
from aerisun.domain.social.schemas import FriendCollectionRead, FriendFeedCollectionRead
from aerisun.domain.social.service import list_public_friend_feed, list_public_friends

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/site", response_model=SiteConfigRead)
def read_site_config(session: Session = Depends(get_session)) -> SiteConfigRead:
    return get_site_config(session)


@router.get("/pages", response_model=PageCollectionRead)
def read_page_copy(session: Session = Depends(get_session)) -> PageCollectionRead:
    return get_page_copy(session)


@router.get("/community-config", response_model=CommunityConfigRead)
def read_community_config(session: Session = Depends(get_session)) -> CommunityConfigRead:
    return get_community_config(session)


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


@router.get("/friends", response_model=FriendCollectionRead)
def read_friends(
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendCollectionRead:
    return list_public_friends(session, limit=limit)


@router.get("/friend-feed", response_model=FriendFeedCollectionRead)
def read_friend_feed(
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendFeedCollectionRead:
    return list_public_friend_feed(session, limit=limit)


@router.get("/guestbook", response_model=GuestbookCollectionRead)
def read_guestbook(
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> GuestbookCollectionRead:
    return list_public_guestbook_entries(session, limit=limit)


@router.post("/guestbook", response_model=GuestbookCreateResponse)
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_guestbook(
    request: Request,
    payload: GuestbookCreate,
    session: Session = Depends(get_session),
) -> GuestbookCreateResponse:
    return create_public_guestbook_entry(session, payload)


@router.get("/comments/{content_type}/{slug}", response_model=CommentCollectionRead)
def read_comments(
    content_type: str,
    slug: str,
    session: Session = Depends(get_session),
) -> CommentCollectionRead:
    try:
        return list_public_comments(session, content_type, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/comments/{content_type}/{slug}", response_model=CommentCreateResponse)
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_comment(
    request: Request,
    content_type: str,
    slug: str,
    payload: CommentCreate,
    session: Session = Depends(get_session),
) -> CommentCreateResponse:
    try:
        return create_public_comment(session, content_type, slug, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reactions", response_model=ReactionRead)
@limiter.limit(RATE_WRITE_REACTION)
def create_reaction(
    request: Request,
    payload: ReactionCreate,
    session: Session = Depends(get_session),
) -> ReactionRead:
    try:
        return register_public_reaction(session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/reactions/{content_type}/{slug}/{reaction_type}", response_model=ReactionRead)
def read_reaction(
    content_type: str,
    slug: str,
    reaction_type: str,
    session: Session = Depends(get_session),
) -> ReactionRead:
    try:
        return read_public_reaction(session, content_type, slug, reaction_type)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/calendar", response_model=CalendarRead)
def read_calendar(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> CalendarRead:
    today = datetime.now(UTC).date()
    start = datetime.fromisoformat(from_date).date() if from_date else today - timedelta(days=180)
    end = datetime.fromisoformat(to_date).date() if to_date else today
    return list_calendar_events(session, start, end)


@router.get("/recent-activity", response_model=RecentActivityRead)
def read_recent_activity(
    limit: int = Query(default=8, ge=1, le=30),
    session: Session = Depends(get_session),
) -> RecentActivityRead:
    return list_recent_activity(session, limit=limit)


@router.get("/activity-heatmap", response_model=ActivityHeatmapRead)
def read_activity_heatmap(
    weeks: int = Query(default=52, ge=1, le=104),
    tz: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ActivityHeatmapRead:
    return build_activity_heatmap(session, weeks=weeks, tz_name=tz)


@router.get("/healthz", response_model=HealthRead)
def healthz() -> HealthRead:
    settings = _get_settings()
    return HealthRead(
        status="ok",
        database_path=str(settings.db_path),
        timestamp=datetime.now(UTC),
    )


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    from aerisun.domain.content.models import PostEntry, DiaryEntry

    settings = _get_settings()
    site_url = settings.site_url.rstrip("/")

    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    urlset = ET.Element("urlset", xmlns=ns)

    def add_url(loc: str, lastmod: datetime | None = None, priority: str = "0.5") -> None:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = f"{site_url}{loc}"
        if lastmod is not None:
            ET.SubElement(url_el, "lastmod").text = lastmod.strftime("%Y-%m-%d")
        ET.SubElement(url_el, "priority").text = priority

    # Static pages
    static_pages = [
        ("/", "1.0"),
        ("/posts", "0.7"),
        ("/diary", "0.7"),
        ("/thoughts", "0.7"),
        ("/excerpts", "0.7"),
        ("/friends", "0.4"),
        ("/guestbook", "0.4"),
        ("/resume", "0.4"),
        ("/calendar", "0.4"),
    ]
    for path, priority in static_pages:
        add_url(path, priority=priority)

    # Dynamic pages – published & public posts
    posts = (
        session.query(PostEntry)
        .filter(PostEntry.status == "published", PostEntry.visibility == "public")
        .all()
    )
    for post in posts:
        mod = post.updated_at or post.created_at
        add_url(f"/posts/{post.slug}", lastmod=mod, priority="0.6")

    # Dynamic pages – published & public diary entries
    diary_entries = (
        session.query(DiaryEntry)
        .filter(DiaryEntry.status == "published", DiaryEntry.visibility == "public")
        .all()
    )
    for entry in diary_entries:
        mod = entry.updated_at or entry.created_at
        add_url(f"/diary/{entry.slug}", lastmod=mod, priority="0.6")

    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        urlset, encoding="unicode"
    )
    return Response(content=xml_string, media_type="application/xml")

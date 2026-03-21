from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from aerisun.activity import build_activity_heatmap, list_calendar_events, list_recent_activity
from aerisun.content import (
    get_public_diary_entry,
    get_public_post,
    list_public_diary_entries,
    list_public_excerpts,
    list_public_posts,
    list_public_thoughts,
)
from aerisun.db import get_session
from aerisun.engagement import (
    create_public_comment,
    create_public_guestbook_entry,
    list_public_comments,
    list_public_guestbook_entries,
    register_public_reaction,
)
from aerisun.modules.site_config import get_page_copy, get_resume, get_site_config
from aerisun.schemas import (
    ActivityHeatmapRead,
    CalendarRead,
    CommentCollectionRead,
    CommentCreate,
    CommentCreateResponse,
    ContentCollectionRead,
    ContentEntryRead,
    FriendCollectionRead,
    FriendFeedCollectionRead,
    GuestbookCollectionRead,
    GuestbookCreate,
    GuestbookCreateResponse,
    HealthRead,
    PageCollectionRead,
    ReactionCreate,
    ReactionRead,
    RecentActivityRead,
    ResumeRead,
    SiteConfigRead,
)
from aerisun.social import list_public_friend_feed, list_public_friends

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
def create_guestbook(
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
def create_comment(
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
def create_reaction(
    payload: ReactionCreate,
    session: Session = Depends(get_session),
) -> ReactionRead:
    try:
        return register_public_reaction(session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/calendar", response_model=CalendarRead)
def read_calendar(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> CalendarRead:
    today = datetime.now(timezone.utc).date()
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
    session: Session = Depends(get_session),
) -> ActivityHeatmapRead:
    return build_activity_heatmap(session, weeks=weeks)


@router.get("/healthz", response_model=HealthRead)
def healthz() -> HealthRead:
    from aerisun.settings import get_settings

    settings = get_settings()
    return HealthRead(
        status="ok",
        database_path=str(settings.db_path),
        timestamp=datetime.now(timezone.utc),
    )

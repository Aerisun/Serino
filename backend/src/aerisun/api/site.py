from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.schemas import HealthRead
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
from aerisun.domain.site_config.schemas import (
    CommunityConfigRead,
    PageCollectionRead,
    ResumeRead,
    SiteConfigRead,
    SitePoemPreviewRead,
)
from aerisun.domain.site_config.service import (
    get_community_config,
    get_page_copy,
    get_resume,
    get_site_config,
    get_site_poem_preview,
)
from aerisun.domain.social.schemas import FriendCollectionRead, FriendFeedCollectionRead
from aerisun.domain.social.service import list_public_friend_feed, list_public_friends

base_router = APIRouter()
router = APIRouter(prefix="/api/v1/site", tags=["site"])


@base_router.get("/site", response_model=SiteConfigRead, summary="获取站点配置")
def read_site_config(session: Session = Depends(get_session)) -> SiteConfigRead:
    return get_site_config(session)


@base_router.get("/pages", response_model=PageCollectionRead, summary="获取页面文案")
def read_page_copy(session: Session = Depends(get_session)) -> PageCollectionRead:
    return get_page_copy(session)


@base_router.get("/community-config", response_model=CommunityConfigRead, summary="获取社区评论配置")
def read_community_config(session: Session = Depends(get_session)) -> CommunityConfigRead:
    return get_community_config(session)


@base_router.get("/resume", response_model=ResumeRead, summary="获取简历数据")
def read_resume(session: Session = Depends(get_session)) -> ResumeRead:
    return get_resume(session)


@base_router.get("/poem-preview", response_model=SitePoemPreviewRead, summary="获取首页诗句预览")
def read_poem_preview(
    response: Response,
    mode: Literal["custom", "hitokoto"] | None = Query(default=None),
    types: list[str] | None = Query(default=None),
    keywords: list[str] | None = Query(default=None),
    strict: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> SitePoemPreviewRead:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return get_site_poem_preview(session, mode=mode, types=types, keywords=keywords, strict=strict)


@base_router.get("/posts", response_model=ContentCollectionRead, summary="获取已发布文章列表")
def read_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_posts(session, limit=limit, offset=offset)


@base_router.get("/posts/{slug}", response_model=ContentEntryRead, summary="获取单篇文章")
def read_post(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    return get_public_post(session, slug)


@base_router.get("/diary", response_model=ContentCollectionRead, summary="获取日记列表")
def read_diary(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_diary_entries(session, limit=limit, offset=offset)


@base_router.get("/diary/{slug}", response_model=ContentEntryRead, summary="获取单篇日记")
def read_diary_entry(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    return get_public_diary_entry(session, slug)


@base_router.get("/thoughts", response_model=ContentCollectionRead, summary="获取想法列表")
def read_thoughts(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_thoughts(session, limit=limit, offset=offset)


@base_router.get("/excerpts", response_model=ContentCollectionRead, summary="获取摘录列表")
def read_excerpts(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_excerpts(session, limit=limit, offset=offset)


@base_router.get("/friends", response_model=FriendCollectionRead, summary="获取友链列表")
def read_friends(
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendCollectionRead:
    return list_public_friends(session, limit=limit)


@base_router.get("/friend-feed", response_model=FriendFeedCollectionRead, summary="获取友链动态")
def read_friend_feed(
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendFeedCollectionRead:
    return list_public_friend_feed(session, limit=limit)


@base_router.get("/calendar", response_model=CalendarRead, summary="获取日历事件")
def read_calendar(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> CalendarRead:
    today = datetime.now(UTC).date()
    start = datetime.fromisoformat(from_date).date() if from_date else today - timedelta(days=180)
    end = datetime.fromisoformat(to_date).date() if to_date else today
    return list_calendar_events(session, start, end)


@base_router.get("/recent-activity", response_model=RecentActivityRead, summary="获取最近动态")
def read_recent_activity(
    limit: int = Query(default=8, ge=1, le=30),
    session: Session = Depends(get_session),
) -> RecentActivityRead:
    return list_recent_activity(session, limit=limit)


@base_router.get("/activity-heatmap", response_model=ActivityHeatmapRead, summary="获取活动热力图")
def read_activity_heatmap(
    weeks: int = Query(default=52, ge=1, le=104),
    tz: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ActivityHeatmapRead:
    return build_activity_heatmap(session, weeks=weeks, tz_name=tz)


@base_router.get("/healthz", response_model=HealthRead, summary="健康检查")
def healthz() -> HealthRead:
    return HealthRead(
        status="ok",
        timestamp=datetime.now(UTC),
    )


router.include_router(base_router)

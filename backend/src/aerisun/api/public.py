from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from aerisun.api.admin.schemas import CommentImageUploadResponse
from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_WRITE_ENGAGEMENT, RATE_WRITE_REACTION, limiter
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


@router.get("/site", response_model=SiteConfigRead, summary="获取站点配置")
def read_site_config(session: Session = Depends(get_session)) -> SiteConfigRead:
    return get_site_config(session)


@router.get("/pages", response_model=PageCollectionRead, summary="获取页面文案")
def read_page_copy(session: Session = Depends(get_session)) -> PageCollectionRead:
    return get_page_copy(session)


@router.get("/community-config", response_model=CommunityConfigRead, summary="获取社区评论配置")
def read_community_config(session: Session = Depends(get_session)) -> CommunityConfigRead:
    return get_community_config(session)


@router.get("/resume", response_model=ResumeRead, summary="获取简历数据")
def read_resume(session: Session = Depends(get_session)) -> ResumeRead:
    return get_resume(session)


@router.get("/posts", response_model=ContentCollectionRead, summary="获取已发布文章列表")
def read_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_posts(session, limit=limit, offset=offset)


@router.get("/posts/{slug}", response_model=ContentEntryRead, summary="获取单篇文章")
def read_post(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    return get_public_post(session, slug)


@router.get("/diary", response_model=ContentCollectionRead, summary="获取日记列表")
def read_diary(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_diary_entries(session, limit=limit, offset=offset)


@router.get("/diary/{slug}", response_model=ContentEntryRead, summary="获取单篇日记")
def read_diary_entry(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    return get_public_diary_entry(session, slug)


@router.get("/thoughts", response_model=ContentCollectionRead, summary="获取想法列表")
def read_thoughts(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_thoughts(session, limit=limit, offset=offset)


@router.get("/excerpts", response_model=ContentCollectionRead, summary="获取摘录列表")
def read_excerpts(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    return list_public_excerpts(session, limit=limit, offset=offset)


@router.get("/friends", response_model=FriendCollectionRead, summary="获取友链列表")
def read_friends(
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendCollectionRead:
    return list_public_friends(session, limit=limit)


@router.get("/friend-feed", response_model=FriendFeedCollectionRead, summary="获取友链动态")
def read_friend_feed(
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendFeedCollectionRead:
    return list_public_friend_feed(session, limit=limit)


@router.get("/guestbook", response_model=GuestbookCollectionRead, summary="获取留言板")
def read_guestbook(
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> GuestbookCollectionRead:
    return list_public_guestbook_entries(session, limit=limit)


@router.post("/guestbook", response_model=GuestbookCreateResponse, summary="提交留言")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_guestbook(
    request: Request,
    payload: GuestbookCreate,
    session: Session = Depends(get_session),
) -> GuestbookCreateResponse:
    return create_public_guestbook_entry(session, payload)


@router.get("/comments/{content_type}/{slug}", response_model=CommentCollectionRead, summary="获取内容评论")
def read_comments(
    content_type: str,
    slug: str,
    session: Session = Depends(get_session),
) -> CommentCollectionRead:
    return list_public_comments(session, content_type, slug)


@router.post("/comments/{content_type}/{slug}", response_model=CommentCreateResponse, summary="发表评论")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_comment(
    request: Request,
    content_type: str,
    slug: str,
    payload: CommentCreate,
    session: Session = Depends(get_session),
) -> CommentCreateResponse:
    return create_public_comment(session, content_type, slug, payload)


@router.post("/reactions", response_model=ReactionRead, summary="提交互动反应")
@limiter.limit(RATE_WRITE_REACTION)
def create_reaction(
    request: Request,
    payload: ReactionCreate,
    session: Session = Depends(get_session),
) -> ReactionRead:
    return register_public_reaction(session, payload)


@router.get(
    "/reactions/{content_type}/{slug}/{reaction_type}",
    response_model=ReactionRead,
    summary="查询反应计数",
)
def read_reaction(
    content_type: str,
    slug: str,
    reaction_type: str,
    session: Session = Depends(get_session),
) -> ReactionRead:
    return read_public_reaction(session, content_type, slug, reaction_type)


@router.post("/comment-image", response_model=CommentImageUploadResponse, summary="评论图片上传")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def upload_comment_image(
    request: Request,
    file: UploadFile,
    session: Session = Depends(get_session),
) -> dict:
    from aerisun.domain.media.service import save_comment_image

    content = file.file.read()
    url = save_comment_image(content, file.filename or "img", file.content_type)
    return {"errno": 0, "data": {"url": url}}


@router.get("/calendar", response_model=CalendarRead, summary="获取日历事件")
def read_calendar(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> CalendarRead:
    today = datetime.now(UTC).date()
    start = datetime.fromisoformat(from_date).date() if from_date else today - timedelta(days=180)
    end = datetime.fromisoformat(to_date).date() if to_date else today
    return list_calendar_events(session, start, end)


@router.get("/recent-activity", response_model=RecentActivityRead, summary="获取最近动态")
def read_recent_activity(
    limit: int = Query(default=8, ge=1, le=30),
    session: Session = Depends(get_session),
) -> RecentActivityRead:
    return list_recent_activity(session, limit=limit)


@router.get("/activity-heatmap", response_model=ActivityHeatmapRead, summary="获取活动热力图")
def read_activity_heatmap(
    weeks: int = Query(default=52, ge=1, le=104),
    tz: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ActivityHeatmapRead:
    return build_activity_heatmap(session, weeks=weeks, tz_name=tz)


@router.get("/healthz", response_model=HealthRead, summary="健康检查")
def healthz() -> HealthRead:
    return HealthRead(
        status="ok",
        timestamp=datetime.now(UTC),
    )


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    from aerisun.core.settings import get_settings as _gs
    from aerisun.domain.content.seo_service import build_sitemap_xml

    settings = _gs()
    site_url = settings.site_url or "https://example.com"
    xml = build_sitemap_xml(session, site_url)
    return Response(content=xml, media_type="application/xml")

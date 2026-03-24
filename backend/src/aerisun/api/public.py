from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from aerisun.api.admin.schemas import CommentImageUploadResponse
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


@router.get("/site", response_model=SiteConfigRead, summary="获取站点配置")
def read_site_config(session: Session = Depends(get_session)) -> SiteConfigRead:
    """返回站点基本信息、导航、社交链接、诗词等公开配置。"""
    return get_site_config(session)


@router.get("/pages", response_model=PageCollectionRead, summary="获取页面文案")
def read_page_copy(session: Session = Depends(get_session)) -> PageCollectionRead:
    """返回各页面的标题、副标题、描述等可配置文案。"""
    return get_page_copy(session)


@router.get("/community-config", response_model=CommunityConfigRead, summary="获取社区评论配置")
def read_community_config(
    session: Session = Depends(get_session),
) -> CommunityConfigRead:
    """返回 Waline 评论系统的前端配置项。"""
    return get_community_config(session)


@router.get("/resume", response_model=ResumeRead, summary="获取简历数据")
def read_resume(session: Session = Depends(get_session)) -> ResumeRead:
    """返回简历基本信息、技能列表和工作经历。"""
    return get_resume(session)


@router.get("/posts", response_model=ContentCollectionRead, summary="获取已发布文章列表")
def read_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    """按发布时间倒序返回公开已发布文章，包含评论数和点赞数。"""
    return list_public_posts(session, limit=limit, offset=offset)


@router.get("/posts/{slug}", response_model=ContentEntryRead, summary="获取单篇文章")
def read_post(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    """根据 slug 返回单篇公开已发布文章的完整内容。"""
    try:
        return get_public_post(session, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/diary", response_model=ContentCollectionRead, summary="获取日记列表")
def read_diary(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    """按发布时间倒序返回公开已发布日记条目。"""
    return list_public_diary_entries(session, limit=limit, offset=offset)


@router.get("/diary/{slug}", response_model=ContentEntryRead, summary="获取单篇日记")
def read_diary_entry(slug: str, session: Session = Depends(get_session)) -> ContentEntryRead:
    """根据 slug 返回单篇公开已发布日记的完整内容。"""
    try:
        return get_public_diary_entry(session, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/thoughts", response_model=ContentCollectionRead, summary="获取想法列表")
def read_thoughts(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    """按发布时间倒序返回公开已发布想法/短文。"""
    return list_public_thoughts(session, limit=limit, offset=offset)


@router.get("/excerpts", response_model=ContentCollectionRead, summary="获取摘录列表")
def read_excerpts(
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> ContentCollectionRead:
    """按发布时间倒序返回公开已发布书摘/引用。"""
    return list_public_excerpts(session, limit=limit, offset=offset)


@router.get("/friends", response_model=FriendCollectionRead, summary="获取友链列表")
def read_friends(
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendCollectionRead:
    """返回已上线的友链列表，按排序权重排列。"""
    return list_public_friends(session, limit=limit)


@router.get("/friend-feed", response_model=FriendFeedCollectionRead, summary="获取友链动态")
def read_friend_feed(
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendFeedCollectionRead:
    """返回友链 RSS 抓取的最新动态列表。"""
    return list_public_friend_feed(session, limit=limit)


@router.get("/guestbook", response_model=GuestbookCollectionRead, summary="获取留言板")
def read_guestbook(
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> GuestbookCollectionRead:
    """返回已审核通过的留言板条目。"""
    return list_public_guestbook_entries(session, limit=limit)


@router.post("/guestbook", response_model=GuestbookCreateResponse, summary="提交留言")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_guestbook(
    request: Request,
    payload: GuestbookCreate,
    session: Session = Depends(get_session),
) -> GuestbookCreateResponse:
    """创建一条新留言，需审核通过后公开显示。"""
    return create_public_guestbook_entry(session, payload)


@router.get(
    "/comments/{content_type}/{slug}",
    response_model=CommentCollectionRead,
    summary="获取内容评论",
)
def read_comments(
    content_type: str,
    slug: str,
    session: Session = Depends(get_session),
) -> CommentCollectionRead:
    """返回指定内容（文章/日记等）下的嵌套评论树。"""
    try:
        return list_public_comments(session, content_type, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/comments/{content_type}/{slug}", response_model=CommentCreateResponse, summary="发表评论")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_comment(
    request: Request,
    content_type: str,
    slug: str,
    payload: CommentCreate,
    session: Session = Depends(get_session),
) -> CommentCreateResponse:
    """在指定内容下发表评论，需审核通过后公开显示。"""
    try:
        return create_public_comment(session, content_type, slug, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reactions", response_model=ReactionRead, summary="提交互动反应")
@limiter.limit(RATE_WRITE_REACTION)
def create_reaction(
    request: Request,
    payload: ReactionCreate,
    session: Session = Depends(get_session),
) -> ReactionRead:
    """为指定内容注册一次互动反应（如点赞），返回当前总数。"""
    try:
        return register_public_reaction(session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    """查询指定内容某种反应类型的当前总数。"""
    try:
        return read_public_reaction(session, content_type, slug, reaction_type)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Comment image upload ──────────────────────────────────────────────

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB hard limit (client compresses before this)


@router.post("/comment-image", response_model=CommentImageUploadResponse, summary="评论图片上传")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def upload_comment_image(
    request: Request,
    file: UploadFile,
    session: Session = Depends(get_session),
) -> dict:
    """Accept a comment image, save to media dir, return its public URL."""
    import hashlib
    from pathlib import Path

    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    content = file.file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="图片过大，请压缩后重试")

    settings = _get_settings()
    media_dir = Path(settings.media_dir).expanduser().resolve() / "comment-images"
    media_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content).hexdigest()[:12]
    ext = (file.filename or "img").rsplit(".", 1)[-1] if file.filename else "jpg"
    filename = f"{sha}.{ext}"
    dest = media_dir / filename

    if not dest.exists():
        with open(dest, "wb") as f:
            f.write(content)

    # Build public URL — served by Caddy / static file handler
    url = f"/media/comment-images/{filename}"
    return {"errno": 0, "data": {"url": url}}


@router.get("/calendar", response_model=CalendarRead, summary="获取日历事件")
def read_calendar(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> CalendarRead:
    """返回指定日期范围内的内容发布事件，用于日历视图。"""
    today = datetime.now(UTC).date()
    start = datetime.fromisoformat(from_date).date() if from_date else today - timedelta(days=180)
    end = datetime.fromisoformat(to_date).date() if to_date else today
    return list_calendar_events(session, start, end)


@router.get("/recent-activity", response_model=RecentActivityRead, summary="获取最近动态")
def read_recent_activity(
    limit: int = Query(default=8, ge=1, le=30),
    session: Session = Depends(get_session),
) -> RecentActivityRead:
    """返回最近的评论、留言和点赞等互动动态。"""
    return list_recent_activity(session, limit=limit)


@router.get("/activity-heatmap", response_model=ActivityHeatmapRead, summary="获取活动热力图")
def read_activity_heatmap(
    weeks: int = Query(default=52, ge=1, le=104),
    tz: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ActivityHeatmapRead:
    """返回指定周数内每日活动计数，用于 GitHub 风格热力图。"""
    return build_activity_heatmap(session, weeks=weeks, tz_name=tz)


@router.get("/healthz", response_model=HealthRead, summary="健康检查")
def healthz() -> HealthRead:
    """返回服务健康状态和数据库路径。"""
    settings = _get_settings()
    return HealthRead(
        status="ok",
        database_path=str(settings.db_path),
        timestamp=datetime.now(UTC),
    )


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    from aerisun.domain.content.models import DiaryEntry, PostEntry

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
    posts = session.query(PostEntry).filter(PostEntry.status == "published", PostEntry.visibility == "public").all()
    for post in posts:
        mod = post.updated_at or post.created_at
        add_url(f"/posts/{post.slug}", lastmod=mod, priority="0.6")

    # Dynamic pages – published & public diary entries
    diary_entries = (
        session.query(DiaryEntry).filter(DiaryEntry.status == "published", DiaryEntry.visibility == "public").all()
    )
    for entry in diary_entries:
        mod = entry.updated_at or entry.created_at
        add_url(f"/diary/{entry.slug}", lastmod=mod, priority="0.6")

    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(urlset, encoding="unicode")
    return Response(content=xml_string, media_type="application/xml")

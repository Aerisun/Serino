from __future__ import annotations

import json
import mimetypes
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from hashlib import sha256
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.params import Depends as DependsMarker
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import (
    get_current_site_session_optional,
    get_current_site_user_optional,
)
from aerisun.core.db import get_session
from aerisun.core.schemas import HealthRead
from aerisun.core.time import beijing_today, shanghai_now
from aerisun.domain.activity.schemas import ActivityHeatmapRead, CalendarRead, RecentActivityRead
from aerisun.domain.activity.service import (
    DEFAULT_ACTIVITY_HEATMAP_TZ,
    build_activity_heatmap,
    list_calendar_events,
    list_recent_activity,
)
from aerisun.domain.content.schemas import ContentCollectionRead, ContentEntryRead
from aerisun.domain.content.service import (
    get_public_diary_entry,
    get_public_post,
    list_public_diary_entries,
    list_public_excerpts,
    list_public_posts,
    list_public_thoughts,
)
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.service import is_site_user_admin
from aerisun.domain.site_config.schemas import (
    CommunityConfigRead,
    LinkPreviewRead,
    PageCollectionRead,
    ResumeRead,
    SiteBootstrapRead,
    SiteConfigRead,
    SitePoemPreviewRead,
)
from aerisun.domain.site_config.service import (
    fetch_site_link_preview_image,
    get_community_config,
    get_page_copy,
    get_resume,
    get_site_bootstrap,
    get_site_config,
    get_site_link_preview,
    get_site_poem_preview,
)
from aerisun.domain.social.schemas import FriendCollectionRead, FriendFeedCollectionRead
from aerisun.domain.social.service import list_public_friend_feed, list_public_friends

base_router = APIRouter()
public_router = APIRouter(tags=["site"])
router = APIRouter(prefix="/api/v1/site", tags=["site"])

BOOTSTRAP_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"
PUBLIC_REVALIDATE_CACHE_CONTROL = "public, max-age=0, must-revalidate"
_LAST_MODIFIED_BY_ETAG: dict[str, datetime] = {}


def _can_view_archived_content(
    session: Session,
    current_user: SiteUser | None,
    current_site_session: SiteUserSession | None,
) -> bool:
    if isinstance(current_user, DependsMarker) or not isinstance(current_user, SiteUser):
        return False
    if isinstance(current_site_session, DependsMarker) or not isinstance(current_site_session, SiteUserSession):
        current_site_session = None
    return current_user is not None and is_site_user_admin(session, current_user, current_site_session)


def _normalize_etag_token(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:].strip()
    return normalized


def _request_is_not_modified(
    request: Request,
    *,
    etag: str,
    last_modified: datetime,
) -> bool:
    if_none_match = request.headers.get("if-none-match", "").strip()
    if if_none_match:
        if if_none_match == "*":
            return True
        normalized_current = _normalize_etag_token(etag)
        if any(_normalize_etag_token(candidate) == normalized_current for candidate in if_none_match.split(",")):
            return True

    if_modified_since = request.headers.get("if-modified-since", "").strip()
    if if_modified_since:
        try:
            parsed = parsedate_to_datetime(if_modified_since)
        except (TypeError, ValueError, IndexError):
            parsed = None

        if parsed is not None:
            normalized_since = parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            if last_modified <= normalized_since.replace(microsecond=0):
                return True
    return False


def _normalize_last_modified_value(value: datetime) -> datetime:
    normalized = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.replace(microsecond=0)


def _resolve_last_modified(etag: str, value: datetime | None) -> datetime:
    if value is not None:
        normalized = _normalize_last_modified_value(value)
        _LAST_MODIFIED_BY_ETAG[etag] = normalized
        return normalized
    cached = _LAST_MODIFIED_BY_ETAG.get(etag)
    if cached is not None:
        return cached
    normalized = _normalize_last_modified_value(shanghai_now())
    _LAST_MODIFIED_BY_ETAG[etag] = normalized
    return normalized


def _latest_payload_datetime(payload: Any) -> datetime | None:
    if isinstance(payload, datetime):
        return payload
    if isinstance(payload, BaseModel):
        return _latest_payload_datetime(payload.model_dump(mode="python"))
    if isinstance(payload, dict):
        latest: datetime | None = None
        for item in payload.values():
            candidate = _latest_payload_datetime(item)
            if candidate is not None and (latest is None or candidate > latest):
                latest = candidate
        return latest
    if isinstance(payload, (list, tuple, set)):
        latest: datetime | None = None
        for item in payload:
            candidate = _latest_payload_datetime(item)
            if candidate is not None and (latest is None or candidate > latest):
                latest = candidate
        return latest
    return None


def _build_conditional_response(
    request: Request | None,
    *,
    content: bytes,
    media_type: str,
    cache_control: str,
    last_modified: datetime | None = None,
) -> Response:
    etag = f'"{sha256(content).hexdigest()}"'
    resolved_last_modified = _resolve_last_modified(etag, last_modified)
    headers = {
        "Cache-Control": cache_control,
        "ETag": etag,
        "Last-Modified": format_datetime(resolved_last_modified, usegmt=True),
    }
    if request is not None and _request_is_not_modified(request, etag=etag, last_modified=resolved_last_modified):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    return Response(content=content, media_type=media_type, headers=headers)


def _build_conditional_json_response(
    request: Request | None,
    *,
    payload: Any,
    cache_control: str = PUBLIC_REVALIDATE_CACHE_CONTROL,
) -> Response:
    encoded_payload = jsonable_encoder(payload)
    content = json.dumps(
        encoded_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _build_conditional_response(
        request,
        content=content,
        media_type="application/json",
        cache_control=cache_control,
        last_modified=_latest_payload_datetime(payload),
    )


@public_router.get("/manifest.webmanifest", summary="获取站点 Web App Manifest")
def read_site_manifest(request: Request, session: Session = Depends(get_session)) -> Response:
    payload = get_site_config(session)
    site = payload.site
    icon_src = str(site.site_icon_url or "").strip()
    icon_type = mimetypes.guess_type(icon_src)[0] if icon_src else None

    manifest = {
        "name": (site.title or site.name or "Aerisun").strip() or "Aerisun",
        "short_name": (site.name or site.title or "Aerisun").strip() or "Aerisun",
        "description": (site.bio or "").strip(),
        "theme_color": "#ffffff",
        "background_color": "#ffffff",
        "display": "standalone",
        "start_url": "/",
        "scope": "/",
        "icons": (
            [
                {
                    "src": icon_src,
                    "sizes": "any",
                    **({"type": icon_type} if icon_type else {}),
                }
            ]
            if icon_src
            else []
        ),
    }
    return _build_conditional_response(
        request,
        content=json.dumps(
            jsonable_encoder(manifest),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
        media_type="application/manifest+json",
        cache_control=PUBLIC_REVALIDATE_CACHE_CONTROL,
    )


@public_router.get("/bootstrap.js", summary="获取首屏运行时配置脚本")
def read_site_bootstrap_script(request: Request, session: Session = Depends(get_session)) -> Response:
    payload = get_site_bootstrap(session)
    serialized = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _build_conditional_response(
        request,
        content=f"window.__AERISUN_BOOTSTRAP__={serialized.replace('</', '<\\/')};".encode(),
        media_type="application/javascript",
        cache_control=BOOTSTRAP_CACHE_CONTROL,
        last_modified=_latest_payload_datetime(payload),
    )


@base_router.get("/site", response_model=SiteConfigRead, summary="获取站点配置")
def read_site_config(request: Request = None, session: Session = Depends(get_session)) -> SiteConfigRead | Response:
    payload = get_site_config(session)
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/pages", response_model=PageCollectionRead, summary="获取页面文案")
def read_page_copy(request: Request = None, session: Session = Depends(get_session)) -> PageCollectionRead | Response:
    payload = get_page_copy(session)
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/community-config", response_model=CommunityConfigRead, summary="获取社区评论配置")
def read_community_config(
    request: Request = None,
    session: Session = Depends(get_session),
) -> CommunityConfigRead | Response:
    payload = get_community_config(session)
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/resume", response_model=ResumeRead, summary="获取简历数据")
def read_resume(request: Request = None, session: Session = Depends(get_session)) -> ResumeRead | Response:
    payload = get_resume(session)
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/bootstrap", response_model=SiteBootstrapRead, summary="获取前端启动配置聚合包")
def read_bootstrap(request: Request = None, session: Session = Depends(get_session)) -> SiteBootstrapRead | Response:
    payload = get_site_bootstrap(session)
    if request is None:
        return payload
    return _build_conditional_json_response(
        request,
        payload=payload,
        cache_control=BOOTSTRAP_CACHE_CONTROL,
    )


@base_router.get("/poem-preview", response_model=SitePoemPreviewRead, summary="获取首页诗句预览")
def read_poem_preview(
    response: Response,
    mode: Literal["custom", "hitokoto"] | None = Query(default=None),
    types: list[str] | None = Query(default=None),
    strict: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> SitePoemPreviewRead:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return get_site_poem_preview(session, mode=mode, types=types, strict=strict)


@base_router.get("/link-preview", response_model=LinkPreviewRead, summary="获取外链预览元信息")
def read_link_preview(url: str = Query(description="需要预览的 http/https 外链")) -> LinkPreviewRead:
    return get_site_link_preview(url)


@base_router.get("/link-preview-image", summary="代理外链预览图片")
def read_link_preview_image(
    url: str = Query(description="外链预览图片地址"),
) -> Response:
    payload, content_type = fetch_site_link_preview_image(url)
    return Response(
        content=payload,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )


@base_router.get("/posts", response_model=ContentCollectionRead, summary="获取已发布文章列表")
def read_posts(
    request: Request = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> ContentCollectionRead | Response:
    payload = list_public_posts(
        session,
        limit=limit,
        offset=offset,
        include_archived=_can_view_archived_content(session, current_user, current_site_session),
    )
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/posts/{slug}", response_model=ContentEntryRead, summary="获取单篇文章")
def read_post(
    slug: str,
    request: Request = None,
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> ContentEntryRead | Response:
    payload = get_public_post(
        session,
        slug,
        include_archived=_can_view_archived_content(session, current_user, current_site_session),
    )
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/diary", response_model=ContentCollectionRead, summary="获取日记列表")
def read_diary(
    request: Request = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> ContentCollectionRead | Response:
    payload = list_public_diary_entries(
        session,
        limit=limit,
        offset=offset,
        include_archived=_can_view_archived_content(session, current_user, current_site_session),
    )
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/diary/{slug}", response_model=ContentEntryRead, summary="获取单篇日记")
def read_diary_entry(
    slug: str,
    request: Request = None,
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> ContentEntryRead | Response:
    payload = get_public_diary_entry(
        session,
        slug,
        include_archived=_can_view_archived_content(session, current_user, current_site_session),
    )
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/thoughts", response_model=ContentCollectionRead, summary="获取碎碎念列表")
def read_thoughts(
    request: Request = None,
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> ContentCollectionRead | Response:
    payload = list_public_thoughts(
        session,
        limit=limit,
        offset=offset,
        include_archived=_can_view_archived_content(session, current_user, current_site_session),
    )
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/excerpts", response_model=ContentCollectionRead, summary="获取文摘列表")
def read_excerpts(
    request: Request = None,
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> ContentCollectionRead | Response:
    payload = list_public_excerpts(
        session,
        limit=limit,
        offset=offset,
        include_archived=_can_view_archived_content(session, current_user, current_site_session),
    )
    if request is None:
        return payload
    return _build_conditional_json_response(request, payload=payload)


@base_router.get("/friends", response_model=FriendCollectionRead, summary="获取友链列表")
def read_friends(
    request: Request = None,
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendCollectionRead | Response:
    payload = list_public_friends(session, limit=limit)
    if request is None:
        return payload
    return _build_conditional_json_response(
        request,
        payload=payload,
    )


@base_router.get("/friend-feed", response_model=FriendFeedCollectionRead, summary="获取友链动态")
def read_friend_feed(
    request: Request = None,
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> FriendFeedCollectionRead | Response:
    payload = list_public_friend_feed(session, limit=limit)
    if request is None:
        return payload
    return _build_conditional_json_response(
        request,
        payload=payload,
    )


@base_router.get("/calendar", response_model=CalendarRead, summary="获取日历事件")
def read_calendar(
    request: Request = None,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> CalendarRead | Response:
    today = beijing_today()
    start = datetime.fromisoformat(from_date).date() if from_date else today - timedelta(days=180)
    end = datetime.fromisoformat(to_date).date() if to_date else today
    payload = list_calendar_events(session, start, end)
    if request is None:
        return payload
    return _build_conditional_json_response(
        request,
        payload=payload,
    )


@base_router.get("/recent-activity", response_model=RecentActivityRead, summary="获取最近动态")
def read_recent_activity(
    request: Request = None,
    limit: int = Query(default=8, ge=1, le=30),
    session: Session = Depends(get_session),
) -> RecentActivityRead | Response:
    payload = list_recent_activity(session, limit=limit)
    if request is None:
        return payload
    return _build_conditional_json_response(
        request,
        payload=payload,
    )


@base_router.get("/activity-heatmap", response_model=ActivityHeatmapRead, summary="获取活动热力图")
def read_activity_heatmap(
    request: Request = None,
    weeks: int = Query(default=52, ge=1, le=104),
    tz: str = Query(default=DEFAULT_ACTIVITY_HEATMAP_TZ),
    session: Session = Depends(get_session),
) -> ActivityHeatmapRead | Response:
    payload = build_activity_heatmap(session, weeks=weeks, tz_name=tz)
    if request is None:
        return payload
    return _build_conditional_json_response(
        request,
        payload=payload,
    )


@base_router.get("/livez", response_model=HealthRead, summary="存活检查")
def livez() -> HealthRead:
    return HealthRead(
        status="ok",
        timestamp=shanghai_now(),
    )


@base_router.get("/readyz", response_model=HealthRead, summary="就绪检查")
def readyz(session: Session = Depends(get_session)) -> HealthRead:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive readiness fallback
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database not ready") from exc

    return HealthRead(
        status="ok",
        timestamp=shanghai_now(),
    )


@base_router.get("/healthz", response_model=HealthRead, summary="健康检查")
def healthz(session: Session = Depends(get_session)) -> HealthRead:
    return readyz(session)


router.include_router(base_router)

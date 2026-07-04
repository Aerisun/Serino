from __future__ import annotations

import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import PROJECT_ROOT, Settings, get_settings
from aerisun.domain.content.feed_service import (
    build_diary_rss_xml,
    build_excerpts_rss_xml,
    build_posts_rss_xml,
    build_thoughts_rss_xml,
)
from aerisun.domain.content.seo_service import (
    build_content_collection_seo_html,
    build_content_detail_seo_html,
    build_friends_seo_html,
    build_guestbook_seo_html,
    build_home_seo_html,
    build_llms_txt,
    build_resume_markdown,
    build_resume_seo_html,
    build_robots_txt,
    build_sitemap_xml,
)

router = APIRouter(tags=["seo"])
html_router = APIRouter(tags=["seo-html"])

_RSS_CONTENT_TYPE = "application/rss+xml; charset=utf-8"
_MARKDOWN_CONTENT_TYPE = "text/markdown; charset=utf-8"
_HTML_CONTENT_TYPE = "text/html; charset=utf-8"
_APP_SHELL_CACHE_TTL = 60.0
_app_shell_cache: dict[str, tuple[float, str]] = {}


def _rss_response(xml: str) -> Response:
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/rss+xml",
        headers={"Content-Type": _RSS_CONTENT_TYPE},
    )


def _markdown_response(content: str | bytes = b"") -> Response:
    body = content.encode("utf-8") if isinstance(content, str) else content
    return Response(
        content=body,
        media_type="text/markdown",
        headers={"Content-Type": _MARKDOWN_CONTENT_TYPE},
    )


def _html_response(content: str) -> Response:
    return Response(
        content=content.encode("utf-8"),
        media_type="text/html",
        headers={"Content-Type": _HTML_CONTENT_TYPE},
    )


def _read_text_file(path: Path) -> str | None:
    try:
        return path.expanduser().read_text(encoding="utf-8")
    except OSError:
        return None


def _cached_http_text(url: str) -> str | None:
    now = time.monotonic()
    cached = _app_shell_cache.get(url)
    if cached and now - cached[0] < _APP_SHELL_CACHE_TTL:
        return cached[1]

    try:
        response = httpx.get(url, timeout=httpx.Timeout(connect=0.5, read=1.5, write=0.5, pool=0.5))
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    if "text/html" not in response.headers.get("content-type", ""):
        return None

    _app_shell_cache[url] = (now, response.text)
    return response.text


def _read_frontend_app_shell(settings: Settings) -> str | None:
    dist_index = settings.frontend_dist_dir / "index.html"
    if content := _read_text_file(dist_index):
        return content

    if settings.frontend_index_url and (content := _cached_http_text(settings.frontend_index_url)):
        return content

    return _read_text_file(PROJECT_ROOT / "frontend" / "index.html")


@html_router.get("/", include_in_schema=False)
def home_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_home_seo_html(
            session,
            site_url,
            api_base_path=settings.api_base_path,
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/resume", include_in_schema=False)
def resume_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_resume_seo_html(
            session,
            site_url,
            api_base_path=settings.api_base_path,
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/posts", include_in_schema=False)
def posts_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_content_collection_seo_html(
            session,
            site_url,
            "posts",
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/diary", include_in_schema=False)
def diary_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_content_collection_seo_html(
            session,
            site_url,
            "diary",
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/thoughts", include_in_schema=False)
def thoughts_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_content_collection_seo_html(
            session,
            site_url,
            "thoughts",
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/excerpts", include_in_schema=False)
def excerpts_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_content_collection_seo_html(
            session,
            site_url,
            "excerpts",
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/friends", include_in_schema=False)
def friends_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_friends_seo_html(
            session,
            site_url,
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/guestbook", include_in_schema=False)
def guestbook_seo_html(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_guestbook_seo_html(
            session,
            site_url,
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/posts/{slug}", include_in_schema=False)
def post_detail_seo_html(slug: str, session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_content_detail_seo_html(
            session,
            site_url,
            "posts",
            slug,
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@html_router.get("/diary/{slug}", include_in_schema=False)
def diary_detail_seo_html(slug: str, session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    return _html_response(
        build_content_detail_seo_html(
            session,
            site_url,
            "diary",
            slug,
            app_shell_html=_read_frontend_app_shell(settings),
        )
    )


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_sitemap_xml(session, site_url)
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt")
def robots_txt() -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    content = build_robots_txt(
        site_url,
        admin_base_path=settings.admin_base_path,
        api_base_path=settings.api_base_path,
    )
    return Response(content=content, media_type="text/plain")


@router.get(
    "/llms.txt",
    response_class=Response,
    responses={
        200: {
            "description": "AI-readable site guide",
            "content": {"text/markdown": {"schema": {"type": "string"}}},
        },
    },
)
def llms_txt(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    content = build_llms_txt(session, site_url, api_base_path=settings.api_base_path)
    return _markdown_response(content)


@router.head("/llms.txt", include_in_schema=False)
def llms_txt_head() -> Response:
    return _markdown_response()


@router.get(
    "/resume.md",
    response_class=Response,
    responses={
        200: {
            "description": "AI-readable Markdown resume",
            "content": {"text/markdown": {"schema": {"type": "string"}}},
        },
    },
)
def resume_markdown(session: Session = Depends(get_session)) -> Response:
    return _markdown_response(build_resume_markdown(session))


@router.head("/resume.md", include_in_schema=False)
def resume_markdown_head() -> Response:
    return _markdown_response()


@router.get("/feeds/posts.xml")
def posts_feed(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_posts_rss_xml(session, site_url)
    return _rss_response(xml)


@router.get("/feeds/diary.xml")
def diary_feed(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_diary_rss_xml(session, site_url)
    return _rss_response(xml)


@router.get("/feeds/thoughts.xml")
def thoughts_feed(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_thoughts_rss_xml(session, site_url)
    return _rss_response(xml)


@router.get("/feeds/excerpts.xml")
def excerpts_feed(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_excerpts_rss_xml(session, site_url)
    return _rss_response(xml)


@router.get("/rss.xml")
def rss_alias(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_posts_rss_xml(session, site_url)
    return _rss_response(xml)


@router.get("/feeds.xml")
def feeds_alias(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_posts_rss_xml(session, site_url)
    return _rss_response(xml)


@router.get("/feed.xml")
def feed_alias(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_posts_rss_xml(session, site_url)
    return _rss_response(xml)

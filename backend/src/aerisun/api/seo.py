from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.content.feed_service import build_posts_rss_xml
from aerisun.domain.content.seo_service import build_robots_txt, build_sitemap_xml

router = APIRouter(tags=["seo"])


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
    content = build_robots_txt(site_url)
    return Response(content=content, media_type="text/plain")


@router.get("/feeds/posts.xml")
def posts_feed(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_posts_rss_xml(session, site_url)
    return Response(content=xml, media_type="application/rss+xml")


@router.get("/rss.xml")
def rss_alias(session: Session = Depends(get_session)) -> Response:
    settings = get_settings()
    site_url = settings.site_url or "https://example.com"
    xml = build_posts_rss_xml(session, site_url)
    return Response(content=xml, media_type="application/rss+xml")

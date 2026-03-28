from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.feed_service import build_posts_rss_xml
from aerisun.domain.content.seo_service import build_robots_txt, build_sitemap_xml
from aerisun.domain.site_config.service import _runtime_site_settings_read

router = APIRouter(tags=["seo"])


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    runtime = _runtime_site_settings_read(session)
    xml = build_sitemap_xml(session, runtime.public_site_url, runtime.sitemap_static_pages)
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt")
def robots_txt(session: Session = Depends(get_session)) -> Response:
    runtime = _runtime_site_settings_read(session)
    content = build_robots_txt(runtime.public_site_url, allow_indexing=runtime.robots_indexing_enabled)
    return Response(content=content, media_type="text/plain")


@router.get("/feeds/posts.xml")
def posts_feed(session: Session = Depends(get_session)) -> Response:
    runtime = _runtime_site_settings_read(session)
    xml = build_posts_rss_xml(
        session,
        runtime.public_site_url,
        channel_title=runtime.rss_title,
        channel_description=runtime.rss_description,
    )
    return Response(content=xml, media_type="application/rss+xml")


@router.get("/rss.xml")
def rss_alias(session: Session = Depends(get_session)) -> Response:
    runtime = _runtime_site_settings_read(session)
    xml = build_posts_rss_xml(
        session,
        runtime.public_site_url,
        channel_title=runtime.rss_title,
        channel_description=runtime.rss_description,
    )
    return Response(content=xml, media_type="application/rss+xml")

from __future__ import annotations

import time
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.content.models import DiaryEntry, PostEntry

router = APIRouter(tags=["seo"])

_sitemap_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 3600  # 1 hour


def _build_sitemap(session: Session) -> str:
    settings = get_settings()
    base_url = settings.site_url.rstrip("/") if settings.site_url else "https://example.com"

    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    # Static pages
    static_pages = [
        ("/", "daily", "1.0"),
        ("/posts", "daily", "0.9"),
        ("/diary", "daily", "0.8"),
        ("/thoughts", "weekly", "0.7"),
        ("/excerpts", "weekly", "0.7"),
        ("/friends", "weekly", "0.6"),
        ("/guestbook", "weekly", "0.5"),
        ("/resume", "monthly", "0.6"),
        ("/calendar", "daily", "0.5"),
    ]

    for path, changefreq, priority in static_pages:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = f"{base_url}{path}"
        SubElement(url_el, "changefreq").text = changefreq
        SubElement(url_el, "priority").text = priority

    # Dynamic content
    content_types = [
        (PostEntry, "posts", "weekly", "0.8"),
        (DiaryEntry, "diary", "monthly", "0.6"),
    ]

    for model, prefix, changefreq, priority in content_types:
        rows = session.execute(
            select(model.slug, model.updated_at).where(
                model.status == "published",
                model.visibility == "public",
            )
        ).all()
        for slug, updated_at in rows:
            url_el = SubElement(urlset, "url")
            SubElement(url_el, "loc").text = f"{base_url}/{prefix}/{slug}"
            if updated_at:
                lastmod = updated_at if isinstance(updated_at, datetime) else datetime.fromisoformat(str(updated_at))
                SubElement(url_el, "lastmod").text = lastmod.strftime("%Y-%m-%d")
            SubElement(url_el, "changefreq").text = changefreq
            SubElement(url_el, "priority").text = priority

    xml_bytes = tostring(urlset, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    now = time.monotonic()
    cached = _sitemap_cache.get("sitemap")
    if cached and (now - cached[0]) < _CACHE_TTL:
        xml = cached[1]
    else:
        xml = _build_sitemap(session)
        _sitemap_cache["sitemap"] = (now, xml)
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt")
def robots_txt() -> Response:
    settings = get_settings()
    base_url = settings.site_url.rstrip("/") if settings.site_url else "https://example.com"
    content = f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"
    return Response(content=content, media_type="text/plain")

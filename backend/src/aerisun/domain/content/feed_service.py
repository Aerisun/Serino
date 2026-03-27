from __future__ import annotations

from datetime import UTC
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy.orm import Session

from aerisun.domain.content.service import list_public_posts


def _strip_html(value: str) -> str:
    text = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    inside_tag = False
    chars: list[str] = []
    for char in text:
        if char == "<":
            inside_tag = True
            continue
        if char == ">":
            inside_tag = False
            continue
        if not inside_tag:
            chars.append(char)
    return " ".join("".join(chars).split())


def build_posts_rss_xml(session: Session, site_url: str, *, limit: int = 20) -> str:
    settings_url = site_url.rstrip("/")
    feed_url = f"{settings_url}/feeds/posts.xml"
    channel_url = f"{settings_url}/posts"
    collection = list_public_posts(session, limit=limit, offset=0)

    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = "Aerisun Posts"
    SubElement(channel, "link").text = channel_url
    SubElement(channel, "description").text = "Latest published posts from Aerisun"
    SubElement(channel, "language").text = "zh-CN"
    SubElement(channel, "generator").text = "Aerisun"
    SubElement(channel, "ttl").text = "60"
    SubElement(
        channel,
        "atom:link",
        {
            "xmlns:atom": "http://www.w3.org/2005/Atom",
            "href": feed_url,
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    latest_updated = None
    for item in collection.items:
        item_url = f"{settings_url}/posts/{item.slug}"
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = item.title
        SubElement(entry, "link").text = item_url
        SubElement(entry, "guid").text = item_url
        description = item.summary or _strip_html(item.body)
        SubElement(entry, "description").text = description

        published_at = item.published_at or item.created_at
        if published_at is not None:
            normalized = published_at.astimezone(UTC) if published_at.tzinfo else published_at.replace(tzinfo=UTC)
            SubElement(entry, "pubDate").text = format_datetime(normalized)
            if latest_updated is None or normalized > latest_updated:
                latest_updated = normalized

    if latest_updated is not None:
        SubElement(channel, "lastBuildDate").text = format_datetime(latest_updated)

    xml = tostring(rss, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml

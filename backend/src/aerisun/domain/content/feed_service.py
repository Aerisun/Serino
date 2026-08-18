from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.core.time import to_beijing_datetime
from aerisun.domain.content.schemas import ContentCollectionRead, ContentSummaryCollectionRead
from aerisun.domain.content.service import (
    list_public_diary_entries,
    list_public_excerpts,
    list_public_thoughts,
    list_rss_posts,
)
from aerisun.domain.diary_access.service import DIARY_PRIVATE_FEATURE_FLAG
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.post_access.service import POST_ACCESS_APPROVAL_FEATURE_FLAG
from aerisun.domain.site_config.models import SiteProfile


@dataclass(frozen=True, slots=True)
class FeedDefinition:
    key: str
    title: str
    description: str
    feed_path: str
    channel_path: str
    item_path_template: str
    list_items: Callable[[Session, int, int], ContentCollectionRead | ContentSummaryCollectionRead]
    limit: int = 20


_FEED_DEFINITIONS: dict[str, FeedDefinition] = {
    "posts": FeedDefinition(
        key="posts",
        title="Aerisun Articles",
        description="Latest published manuscripts and notes from Aerisun",
        feed_path="/feeds/articles.xml",
        channel_path="/posts",
        item_path_template="/posts/{slug}",
        list_items=list_rss_posts,
        limit=20,
    ),
    "diary": FeedDefinition(
        key="diary",
        title="Aerisun Diary",
        description="Latest published diary entries from Aerisun",
        feed_path="/feeds/diary.xml",
        channel_path="/diary",
        item_path_template="/diary/{slug}",
        list_items=list_public_diary_entries,
        limit=20,
    ),
    "thoughts": FeedDefinition(
        key="thoughts",
        title="Aerisun Thoughts",
        description="Latest published thoughts from Aerisun",
        feed_path="/feeds/thoughts.xml",
        channel_path="/thoughts",
        item_path_template="/thoughts#{slug}",
        list_items=list_public_thoughts,
        limit=40,
    ),
    "excerpts": FeedDefinition(
        key="excerpts",
        title="Aerisun Excerpts",
        description="Latest published excerpts from Aerisun",
        feed_path="/feeds/excerpts.xml",
        channel_path="/excerpts",
        item_path_template="/excerpts#{slug}",
        list_items=list_public_excerpts,
        limit=40,
    ),
}


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


def list_feed_definitions() -> list[FeedDefinition]:
    # Keep the static definition list for admin/OpenAPI callers. Public guidance
    # filters diary feeds in SEO/LLM builders when diary privacy is enabled.
    return [
        _FEED_DEFINITIONS["posts"],
        _FEED_DEFINITIONS["diary"],
        _FEED_DEFINITIONS["thoughts"],
        _FEED_DEFINITIONS["excerpts"],
    ]


def get_feed_definition(feed_key: str) -> FeedDefinition:
    try:
        return _FEED_DEFINITIONS[feed_key]
    except KeyError as exc:  # pragma: no cover - internal misuse guard
        raise ValidationError(f"Unsupported feed key: {feed_key}") from exc


def _feed_item_path(definition: FeedDefinition, item: object) -> str:
    if definition.key == "posts" and getattr(item, "kind", "manuscript") == "note":
        return f"/notes/{item.slug}"
    return definition.item_path_template.format(slug=item.slug)


def build_feed_rss_xml(session: Session, site_url: str, feed_key: str, *, limit: int | None = None) -> str:
    definition = get_feed_definition(feed_key)
    profile = session.scalar(select(SiteProfile).order_by(SiteProfile.created_at.asc()).limit(1))
    site_name = ((profile.name or profile.title).strip() if profile is not None else "") or "Site"
    feature_flags = profile.feature_flags if profile is not None and isinstance(profile.feature_flags, dict) else {}
    diary_private = bool(feature_flags.get(DIARY_PRIVATE_FEATURE_FLAG, True))
    post_approval_enabled = bool(feature_flags.get(POST_ACCESS_APPROVAL_FEATURE_FLAG, True))
    settings_url = site_url.rstrip("/")
    feed_url = f"{settings_url}{definition.feed_path}"
    channel_url = f"{settings_url}{definition.channel_path}"
    if definition.key == "diary" and diary_private:
        collection = None
    elif definition.key == "posts":
        collection = list_rss_posts(
            session,
            limit=limit or definition.limit,
            offset=0,
            exclude_requires_approval=post_approval_enabled,
        )
    else:
        collection = definition.list_items(
            session,
            limit=limit or definition.limit,
            offset=0,
        )

    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    section_title = {
        "posts": "Articles",
        "diary": "Diary",
        "thoughts": "Thoughts",
        "excerpts": "Excerpts",
    }[definition.key]
    content_label = {
        "posts": "manuscripts and notes",
        "diary": "diary entries",
        "thoughts": "thoughts",
        "excerpts": "excerpts",
    }[definition.key]
    SubElement(channel, "title").text = f"{site_name} {section_title}"
    SubElement(channel, "link").text = channel_url
    SubElement(channel, "description").text = f"Latest published {content_label} from {site_name}"
    SubElement(channel, "language").text = "zh-CN"
    SubElement(channel, "generator").text = "Serino"
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
    collection_items = collection.items if collection is not None else []
    for item in collection_items:
        item_url = f"{settings_url}{_feed_item_path(definition, item)}"
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = item.title
        SubElement(entry, "link").text = item_url
        SubElement(entry, "guid").text = item_url
        body = getattr(item, "body", "")
        description = item.summary or _strip_html(body)
        SubElement(entry, "description").text = description

        published_at = item.published_at or item.created_at
        if published_at is not None:
            normalized = to_beijing_datetime(published_at)
            SubElement(entry, "pubDate").text = format_datetime(normalized)
            if latest_updated is None or normalized > latest_updated:
                latest_updated = normalized

    if latest_updated is not None:
        SubElement(channel, "lastBuildDate").text = format_datetime(latest_updated)

    xml = tostring(rss, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


def build_posts_rss_xml(session: Session, site_url: str, *, limit: int = 20) -> str:
    return build_feed_rss_xml(session, site_url, "posts", limit=limit)


def build_diary_rss_xml(session: Session, site_url: str, *, limit: int = 20) -> str:
    return build_feed_rss_xml(session, site_url, "diary", limit=limit)


def build_thoughts_rss_xml(session: Session, site_url: str, *, limit: int = 40) -> str:
    return build_feed_rss_xml(session, site_url, "thoughts", limit=limit)


def build_excerpts_rss_xml(session: Session, site_url: str, *, limit: int = 40) -> str:
    return build_feed_rss_xml(session, site_url, "excerpts", limit=limit)

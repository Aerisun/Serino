from __future__ import annotations

import json
import re
import time
from datetime import datetime
from html import escape
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.diary_access.service import diary_private_enabled
from aerisun.domain.engagement.service import list_public_guestbook_entries
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.site_config.models import PageCopy, ResumeBasics, SiteProfile, SocialLink
from aerisun.domain.social.models import Friend, FriendFeedItem, FriendFeedSource

_sitemap_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 3600  # 1 hour


def build_sitemap_xml(session: Session, site_url: str) -> str:
    """Build sitemap XML string. Uses module-level caching with 1-hour TTL."""
    now = time.monotonic()
    include_diary = not diary_private_enabled(session)
    cache_key = f"sitemap:{site_url.rstrip('/')}:{int(include_diary)}"
    cached = _sitemap_cache.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    base_url = site_url.rstrip("/")
    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    static_pages = [
        ("/", "daily", "1.0"),
        ("/posts", "daily", "0.9"),
        ("/thoughts", "weekly", "0.7"),
        ("/excerpts", "weekly", "0.7"),
        ("/friends", "weekly", "0.6"),
        ("/guestbook", "weekly", "0.5"),
        ("/resume", "monthly", "0.6"),
    ]
    if include_diary:
        static_pages.insert(2, ("/diary", "daily", "0.8"))

    for path, changefreq, priority in static_pages:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = f"{base_url}{path}"
        SubElement(url_el, "changefreq").text = changefreq
        SubElement(url_el, "priority").text = priority

    content_types = [
        (PostEntry, "posts", "weekly", "0.8"),
    ]
    if include_diary:
        content_types.append((DiaryEntry, "diary", "monthly", "0.6"))

    for model, prefix, changefreq, priority in content_types:
        rows = session.execute(
            select(model.slug, model.updated_at).where(
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
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
    _sitemap_cache[cache_key] = (now, xml)
    return xml


def _normalize_robots_path(value: str, fallback: str) -> str:
    normalized = (value or fallback).strip() or fallback
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized if normalized.endswith("/") else f"{normalized}/"


def build_robots_txt(
    site_url: str,
    *,
    admin_base_path: str = "/admin/",
    api_base_path: str = "/api",
    diary_private: bool = False,
) -> str:
    base_url = site_url.rstrip("/")
    admin_path = _normalize_robots_path(admin_base_path, "/admin/")
    api_path = _normalize_robots_path(api_base_path, "/api")
    admin_path_without_slash = admin_path.rstrip("/")
    admin_api_path = f"{api_path}v1/admin"
    protected_paths = [
        f"Disallow: {admin_path_without_slash}",
        f"Disallow: {admin_path}",
        f"Disallow: {admin_api_path}",
        f"Disallow: {api_path}v1/admin/",
        "Disallow: /api/mcp",
    ]
    if diary_private:
        protected_paths.extend(
            [
                "Disallow: /diary",
                "Disallow: /diary/",
                f"Disallow: {api_path}v1/site/diary",
                f"Disallow: {api_path}v1/site/diary/",
            ]
        )
    allowed_search_agents = [
        "Googlebot",
        "bingbot",
        "Baiduspider",
        "Bytespider",
        "DoubaoBot",
        "OAI-SearchBot",
        "ChatGPT-User",
        "PerplexityBot",
        "Claude-SearchBot",
        "Claude-User",
        "GoogleOther",
        "Google-InspectionTool",
        "Google-Agent",
        "Google-NotebookLM",
        "Google-Read-Aloud",
    ]
    groups: list[str] = []

    for user_agent in allowed_search_agents:
        groups.append(
            "\n".join(
                [
                    f"User-agent: {user_agent}",
                    "Allow: /",
                    *protected_paths,
                ]
            )
        )

    groups.append(
        "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                *protected_paths,
            ]
        )
    )

    return "\n\n".join([*groups, f"Sitemap: {base_url}/sitemap.xml"]) + "\n"


def _clean_llms_text(value: object, *, max_length: int = 280) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1].rstrip()}…"


def _markdown_label(value: object, fallback: str) -> str:
    label = _clean_llms_text(value, max_length=90) or fallback
    return label.replace("[", "(").replace("]", ")")


def _markdown_note(value: object, *, max_length: int = 180) -> str:
    note = _clean_llms_text(value, max_length=max_length)
    return note.replace("```", " ").replace("`", "").replace("[", "(").replace("]", ")").replace("|", "/").strip()


def _internal_url(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{normalized_path}"


def _public_link(base_url: str, href: str) -> str:
    value = (href or "").strip()
    if not value:
        return base_url
    if value.startswith(("http://", "https://", "mailto:", "tel:")):
        return value
    if "@" in value and "/" not in value:
        return f"mailto:{value}"
    return _internal_url(base_url, value)


def _html_attr(value: object) -> str:
    return escape(str(value or ""), quote=True)


def _html_text(value: object) -> str:
    return escape(str(value or ""))


def _json_ld_script(data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


_DEFAULT_APP_SHELL_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="/bootstrap.js"></script>
</head>
<body>
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
</body>
</html>
"""


def _compact_json_ld(value: object) -> object:
    if isinstance(value, dict):
        compacted = {key: _compact_json_ld(entry) for key, entry in value.items()}
        return {key: entry for key, entry in compacted.items() if entry not in ("", None, [], {})}
    if isinstance(value, list):
        compacted_list = [_compact_json_ld(entry) for entry in value]
        return [entry for entry in compacted_list if entry not in ("", None, [], {})]
    return value


def _plain_text(value: object, *, max_length: int = 280) -> str:
    text = str(value or "")
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`~-]+", " ", text)
    return _clean_llms_text(text, max_length=max_length)


def _has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _identity_label(real_name: str, nickname: str) -> str:
    real = _clean_llms_text(real_name, max_length=120)
    alias = _clean_llms_text(nickname, max_length=120)
    if not real or not alias or real == alias:
        return real
    if _has_cjk(real):
        return f"{real}（{alias}）"
    return f"{real} ({alias})"


def _strengthen_identity_description(description: str, *, real_name: str, nickname: str, max_length: int) -> str:
    text = _clean_llms_text(description, max_length=max_length)
    label = _identity_label(real_name, nickname)
    if not label or label == real_name:
        return text
    if real_name in text and nickname in text:
        return text
    separator = "。" if _has_cjk(real_name) else "."
    strengthened = f"{label}{separator} {text}" if text else label
    return _clean_llms_text(strengthened, max_length=max_length)


def _identity_bridge_sentence(real_name: str, nickname: str) -> str:
    real = _clean_llms_text(real_name, max_length=120)
    alias = _clean_llms_text(nickname, max_length=120)
    if not real or not alias or real == alias:
        return ""
    if _has_cjk(real):
        return f"{alias} 是 {real} 的个人网站、博客和公开作品入口。"
    return f"This is the personal website, blog, and public work archive for {real} ({alias})."


def _canonical_base_url(site_url: str, search_config: dict[str, object]) -> str:
    canonical_url = _clean_llms_text(search_config.get("canonical_url"), max_length=500)
    return (canonical_url or site_url or "https://example.com").rstrip("/")


def _read_search_optimization(profile: SiteProfile | None) -> dict[str, object]:
    if not profile or not isinstance(profile.feature_flags, dict):
        return {}
    raw = profile.feature_flags.get("search_optimization")
    return raw if isinstance(raw, dict) else {}


def _read_text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean_llms_text(item, max_length=80) for item in value if _clean_llms_text(item, max_length=80)]
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.replace("，", ",").replace("\n", ",").split(",") if item.strip()]


def _unique_links(base_url: str, values: list[str]) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for value in values:
        link = _public_link(base_url, value)
        if link and link not in seen:
            links.append(link)
            seen.add(link)
    return links


def _read_public_identity(session: Session, site_url: str) -> dict[str, object]:
    profile = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    resume = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
    social_links = session.scalars(
        select(SocialLink).order_by(SocialLink.order_index.asc(), SocialLink.created_at.asc()).limit(12)
    ).all()
    search_config = _read_search_optimization(profile)
    base_url = _canonical_base_url(site_url, search_config)
    real_name = (
        _clean_llms_text(search_config.get("real_name"), max_length=120)
        or _clean_llms_text(resume.title if resume else "", max_length=120)
        or _clean_llms_text(profile.name if profile else "", max_length=120)
        or "Site owner"
    )
    search_title = _clean_llms_text(search_config.get("meta_title"), max_length=160)
    site_title = (
        _clean_llms_text(profile.title if profile else "", max_length=160)
        or _clean_llms_text(profile.name if profile else "", max_length=160)
        or search_title
        or real_name
    )
    nickname = (
        site_title if site_title != real_name else _clean_llms_text(profile.name if profile else "", max_length=120)
    )
    identity_summary = (
        _clean_llms_text(search_config.get("llm_summary"), max_length=420)
        or _clean_llms_text(search_config.get("meta_description"), max_length=420)
        or _clean_llms_text(profile.bio if profile else "", max_length=420)
        or _plain_text(resume.summary if resume else "", max_length=420)
        or f"Public personal website and blog for {real_name}."
    )
    identity_summary = _strengthen_identity_description(
        identity_summary,
        real_name=real_name,
        nickname=nickname,
        max_length=420,
    )
    search_description = (
        _clean_llms_text(search_config.get("meta_description"), max_length=280)
        or _clean_llms_text(profile.bio if profile else "", max_length=280)
        or _plain_text(resume.summary if resume else "", max_length=280)
        or identity_summary
    )
    search_description = _strengthen_identity_description(
        search_description,
        real_name=real_name,
        nickname=nickname,
        max_length=280,
    )
    same_as_values = [
        *_read_text_list(search_config.get("same_as")),
        *[_clean_llms_text(link.href, max_length=500) for link in social_links],
    ]
    image = ""
    if resume and resume.profile_image_url:
        image = _public_link(base_url, resume.profile_image_url)
    elif profile and profile.og_image:
        image = _public_link(base_url, profile.og_image)

    return {
        "base_url": base_url,
        "profile": profile,
        "resume": resume,
        "social_links": social_links,
        "search_config": search_config,
        "real_name": real_name,
        "site_title": site_title,
        "search_title": search_title,
        "nickname": nickname,
        "identity_label": _identity_label(real_name, nickname),
        "identity_bridge_sentence": _identity_bridge_sentence(real_name, nickname),
        "search_description": search_description,
        "identity_summary": identity_summary,
        "expertise": _read_text_list(search_config.get("expertise")),
        "keywords": _read_text_list(search_config.get("keywords")),
        "same_as": _unique_links(base_url, same_as_values),
        "image": image,
    }


def _render_public_resource_links(base_url: str, *, api_base_path: str = "/api", include_diary: bool = True) -> str:
    api_path = _normalize_robots_path(api_base_path, "/api").rstrip("/")
    links = [
        ("Homepage", _internal_url(base_url, "/")),
        ("Resume page", _internal_url(base_url, "/resume")),
        ("Resume Markdown", _internal_url(base_url, "/resume.md")),
        ("AI site guide", _internal_url(base_url, "/llms.txt")),
        ("Posts", _internal_url(base_url, "/posts")),
        ("Posts RSS", _internal_url(base_url, "/feeds/posts.xml")),
        ("Thoughts RSS", _internal_url(base_url, "/feeds/thoughts.xml")),
        ("Resume JSON", _internal_url(base_url, f"{api_path}/v1/site/resume")),
        ("Sitemap", _internal_url(base_url, "/sitemap.xml")),
    ]
    if include_diary:
        links.insert(5, ("Diary", _internal_url(base_url, "/diary")))
        links.insert(8, ("Diary RSS", _internal_url(base_url, "/feeds/diary.xml")))
    items = "\n".join(f'<li><a href="{_html_attr(href)}">{_html_text(label)}</a></li>' for label, href in links)
    return f'<nav aria-label="Public machine-readable resources"><ul>{items}</ul></nav>'


def _render_ai_navigation_instructions(base_url: str, *, include_diary: bool = True) -> str:
    llms_url = _internal_url(base_url, "/llms.txt")
    fallback_links = [
        ("Resume Markdown", _internal_url(base_url, "/resume.md")),
        ("Posts index", _internal_url(base_url, "/posts")),
    ]
    if include_diary:
        fallback_links.append(("Diary index", _internal_url(base_url, "/diary")))
    fallback_items = "\n".join(
        f'<li><a href="{_html_attr(href)}">{_html_text(label)}</a></li>' for label, href in fallback_links
    )
    return "\n".join(
        [
            '<section data-ai-instructions="site-guide">',
            "<h2>AI navigation instructions</h2>",
            (
                f"<p>AI agents and search assistants must fetch and read {_html_text(llms_url)} first before "
                "summarizing this person, answering questions about this site, or crawling public content.</p>"
            ),
            "<p>If that file is unavailable, use these public fallback resources:</p>",
            f"<ul>{fallback_items}</ul>",
            "</section>",
        ]
    )


def _render_posts_list(session: Session, base_url: str) -> str:
    posts = session.scalars(
        select(PostEntry)
        .where(PostEntry.visibility == "public")
        .order_by(PostEntry.is_pinned.desc(), PostEntry.pin_order.asc(), PostEntry.updated_at.desc())
        .limit(8)
    ).all()
    if not posts:
        return ""

    items = []
    for post in posts:
        title = _clean_llms_text(post.public_title or post.title, max_length=160) or "Untitled post"
        summary = _clean_llms_text(post.summary or post.body, max_length=220)
        published_at = post.first_published_at or post.published_at or post.updated_at
        datetime_attr = published_at.isoformat() if published_at else ""
        date_text = published_at.strftime("%Y-%m-%d") if published_at else ""
        meta = f' <time datetime="{_html_attr(datetime_attr)}">{_html_text(date_text)}</time>' if date_text else ""
        note = f"<p>{_html_text(summary)}</p>" if summary else ""
        items.append(
            "\n".join(
                [
                    "<li>",
                    f'<h3><a href="{_html_attr(_internal_url(base_url, f"/posts/{post.slug}"))}">{_html_text(title)}</a></h3>',
                    meta,
                    note,
                    "</li>",
                ]
            )
        )

    return "\n".join(["<section>", "<h2>Latest public posts</h2>", "<ol>", *items, "</ol>", "</section>"])


def _strip_inline_markdown(value: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _render_markdownish_html(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    html_parts: list[str] = []
    list_open = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html_parts.append("</ul>")
            list_open = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            close_list()
            continue
        if stripped.startswith("#"):
            close_list()
            level = min(len(stripped) - len(stripped.lstrip("#")) + 1, 4)
            text = stripped.lstrip("#").strip()
            html_parts.append(f"<h{level}>{_html_text(_strip_inline_markdown(text))}</h{level}>")
            continue
        if stripped.startswith("- "):
            if not list_open:
                html_parts.append("<ul>")
                list_open = True
            html_parts.append(f"<li>{_html_text(_strip_inline_markdown(stripped[2:].strip()))}</li>")
            continue
        close_list()
        html_parts.append(f"<p>{_html_text(_strip_inline_markdown(stripped))}</p>")

    close_list()
    return "\n".join(html_parts)


_CONTENT_SEO_CONFIG: dict[str, dict[str, object]] = {
    "posts": {
        "model": PostEntry,
        "page_key": "posts",
        "title": "Posts",
        "description": "Public long-form posts and project notes.",
        "path": "/posts",
        "detail_path_template": "/posts/{slug}",
        "feed_path": "/feeds/posts.xml",
        "limit": 20,
        "include_body_in_collection": False,
        "schema_type": "BlogPosting",
        "detail_shell_key": "post-detail",
    },
    "diary": {
        "model": DiaryEntry,
        "page_key": "diary",
        "title": "Diary",
        "description": "Public diary entries.",
        "path": "/diary",
        "detail_path_template": "/diary/{slug}",
        "feed_path": "/feeds/diary.xml",
        "limit": 20,
        "include_body_in_collection": False,
        "schema_type": "BlogPosting",
        "detail_shell_key": "diary-detail",
    },
    "thoughts": {
        "model": ThoughtEntry,
        "page_key": "thoughts",
        "title": "Thoughts",
        "description": "Public short notes.",
        "path": "/thoughts",
        "detail_path_template": "/thoughts#{slug}",
        "feed_path": "/feeds/thoughts.xml",
        "limit": 40,
        "include_body_in_collection": True,
        "schema_type": "SocialMediaPosting",
        "detail_shell_key": "thought-detail",
    },
    "excerpts": {
        "model": ExcerptEntry,
        "page_key": "excerpts",
        "title": "Excerpts",
        "description": "Public excerpts and reading notes.",
        "path": "/excerpts",
        "detail_path_template": "/excerpts#{slug}",
        "feed_path": "/feeds/excerpts.xml",
        "limit": 40,
        "include_body_in_collection": True,
        "schema_type": "Article",
        "detail_shell_key": "excerpt-detail",
    },
}


def _content_config(content_type: str) -> dict[str, object]:
    try:
        return _CONTENT_SEO_CONFIG[content_type]
    except KeyError as exc:
        raise ResourceNotFound(f"content type '{content_type}' is not available") from exc


def _content_entry_title(item: object) -> str:
    return (
        _clean_llms_text(
            getattr(item, "public_title", None) or getattr(item, "title", ""),
            max_length=180,
        )
        or "Untitled"
    )


def _content_entry_summary(item: object, *, max_length: int = 260) -> str:
    return (
        _clean_llms_text(getattr(item, "summary", ""), max_length=max_length)
        or _plain_text(getattr(item, "body", ""), max_length=max_length)
        or "No summary is available."
    )


def _content_entry_timestamp(item: object, attr_name: str) -> datetime | None:
    value = getattr(item, attr_name, None)
    return value if isinstance(value, datetime) else None


def _content_entry_url(base_url: str, config: dict[str, object], slug: str) -> str:
    template = str(config["detail_path_template"])
    return _internal_url(base_url, template.format(slug=slug))


def _content_page_copy(session: Session, config: dict[str, object]) -> tuple[str, str]:
    page_key = str(config["page_key"])
    page = session.scalar(select(PageCopy).where(PageCopy.page_key == page_key).limit(1))
    title = _clean_llms_text(page.title if page else "", max_length=160) or str(config["title"])
    description = _clean_llms_text(page.subtitle if page else "", max_length=260) or str(config["description"])
    return title, description


def _content_entries(session: Session, config: dict[str, object]) -> list[object]:
    model = config["model"]
    limit = int(config["limit"])
    return list(
        session.scalars(
            select(model)
            .where(model.visibility == "public")
            .order_by(
                model.is_pinned.desc(),
                model.pin_order.asc(),
                model.updated_at.desc(),
            )
            .limit(limit)
        ).all()
    )


def _content_entry(session: Session, config: dict[str, object], slug: str) -> object:
    model = config["model"]
    item = session.scalar(select(model).where(model.visibility == "public", model.slug == slug).limit(1))
    if item is None:
        raise ResourceNotFound(f"content item '{slug}' is not available")
    return item


def _render_content_entry_html(
    item: object,
    *,
    base_url: str,
    config: dict[str, object],
    heading_level: int,
    include_body: bool,
) -> str:
    slug = str(getattr(item, "slug", ""))
    title = _content_entry_title(item)
    summary = _content_entry_summary(item)
    item_url = _content_entry_url(base_url, config, slug)
    published_at = _content_entry_timestamp(item, "published_at") or _content_entry_timestamp(item, "created_at")
    updated_at = _content_entry_timestamp(item, "updated_at")
    tags = getattr(item, "tags", []) if isinstance(getattr(item, "tags", []), list) else []
    category = _clean_llms_text(getattr(item, "category", ""), max_length=100)
    h_tag = f"h{heading_level}"
    published_html = ""
    if published_at:
        published_html = f'<time datetime="{_html_attr(published_at.isoformat())}">{_html_text(published_at.strftime("%Y-%m-%d"))}</time>'
    updated_html = ""
    if updated_at:
        updated_html = f'<time datetime="{_html_attr(updated_at.isoformat())}">{_html_text(updated_at.strftime("%Y-%m-%d"))}</time>'
    meta_parts = [
        f"Published: {published_html}" if published_html else "",
        f"Updated: {updated_html}" if updated_html else "",
        f"Category: {_html_text(category)}" if category else "",
        f"Tags: {_html_text(', '.join(str(tag) for tag in tags))}" if tags else "",
    ]
    meta_html = " · ".join(part for part in meta_parts if part)
    body_html = ""
    if include_body:
        body_html = "\n".join(
            [
                "<section>",
                "<h4>Content</h4>",
                _render_markdownish_html(str(getattr(item, "body", ""))),
                "</section>",
            ]
        )

    return "\n".join(
        [
            f'<article id="{_html_attr(slug)}">',
            f'<{h_tag}><a href="{_html_attr(item_url)}">{_html_text(title)}</a></{h_tag}>',
            f"<p>{meta_html}</p>" if meta_html else "",
            f"<p>{_html_text(summary)}</p>",
            f'<p>Canonical public URL: <a href="{_html_attr(item_url)}">{_html_text(item_url)}</a></p>',
            body_html,
            "</article>",
        ]
    )


def _content_list_json_ld(
    entries: list[object], *, base_url: str, config: dict[str, object]
) -> list[dict[str, object]]:
    items = []
    for index, item in enumerate(entries, start=1):
        slug = str(getattr(item, "slug", ""))
        item_url = _content_entry_url(base_url, config, slug)
        published_at = _content_entry_timestamp(item, "published_at") or _content_entry_timestamp(item, "created_at")
        updated_at = _content_entry_timestamp(item, "updated_at")
        items.append(
            {
                "@type": "ListItem",
                "position": index,
                "url": item_url,
                "item": _compact_json_ld(
                    {
                        "@type": config["schema_type"],
                        "headline": _content_entry_title(item),
                        "url": item_url,
                        "description": _content_entry_summary(item),
                        "datePublished": published_at.isoformat() if published_at else "",
                        "dateModified": updated_at.isoformat() if updated_at else "",
                        "keywords": getattr(item, "tags", []),
                    }
                ),
            }
        )
    return items


def build_content_collection_seo_html(
    session: Session,
    site_url: str,
    content_type: str,
    *,
    app_shell_html: str | None = None,
) -> str:
    """Build crawler-readable HTML for public content collection pages."""
    config = _content_config(content_type)
    diary_private = content_type == "diary" and diary_private_enabled(session)
    identity = _read_public_identity(session, site_url)
    base_url = str(identity["base_url"])
    site_title = str(identity["site_title"])
    real_name = str(identity["real_name"])
    page_title, page_description = _content_page_copy(session, config)
    canonical_path = str(config["path"])
    canonical_url = _internal_url(base_url, canonical_path)
    entries = [] if diary_private else _content_entries(session, config)
    include_body = bool(config["include_body_in_collection"])
    entries_html = (
        "<p>Diary details are private and are not available to crawlers.</p>"
        if diary_private
        else "\n".join(
            _render_content_entry_html(
                item,
                base_url=base_url,
                config=config,
                heading_level=2,
                include_body=include_body,
            )
            for item in entries
        )
    )
    feed_path = str(config["feed_path"])
    alternate_links = (
        []
        if diary_private
        else [
            ("application/rss+xml", _internal_url(base_url, feed_path), f"{page_title} RSS"),
        ]
    )
    feed_html = (
        ""
        if diary_private
        else (
            f'<p>AI-readable feed: <a href="{_html_attr(_internal_url(base_url, feed_path))}">'
            f"{_html_text(_internal_url(base_url, feed_path))}</a></p>"
        )
    )

    json_ld = _compact_json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "@id": f"{canonical_url}#page",
                    "url": canonical_url,
                    "name": page_title,
                    "description": page_description,
                    "isPartOf": {"@id": f"{base_url}/#website"},
                    "publisher": {"@id": f"{base_url}/#person"},
                    "mainEntity": {"@id": f"{canonical_url}#items"},
                },
                {
                    "@type": "ItemList",
                    "@id": f"{canonical_url}#items",
                    "name": page_title,
                    "numberOfItems": len(entries),
                    "itemListElement": _content_list_json_ld(entries, base_url=base_url, config=config),
                },
            ],
        }
    )

    body_html = "\n".join(
        [
            "<main>",
            f"<h1>{_html_text(page_title)}</h1>",
            f"<p>{_html_text(page_description)}</p>",
            feed_html,
            entries_html or "<p>No public content is available.</p>",
            "</main>",
        ]
    )

    return _build_html_document(
        title=f"{page_title} · {site_title}" if site_title else page_title,
        description=page_description,
        canonical_url=canonical_url,
        site_name=site_title,
        body_html=body_html,
        json_ld=json_ld,
        image=str(identity["image"]),
        author=real_name,
        keywords=list(identity["keywords"]) if isinstance(identity["keywords"], list) else [],
        app_shell_html=app_shell_html,
        shell_key=content_type,
        alternate_links=alternate_links,
    )


def build_content_detail_seo_html(
    session: Session,
    site_url: str,
    content_type: str,
    slug: str,
    *,
    app_shell_html: str | None = None,
) -> str:
    """Build crawler-readable HTML for public post and diary detail pages."""
    if content_type not in {"posts", "diary"}:
        raise ResourceNotFound(f"content detail '{content_type}' is not available")
    config = _content_config(content_type)
    identity = _read_public_identity(session, site_url)
    base_url = str(identity["base_url"])
    site_title = str(identity["site_title"])
    real_name = str(identity["real_name"])
    if content_type == "diary" and diary_private_enabled(session):
        canonical_url = _internal_url(base_url, "/diary")
        title = "Diary"
        description = "Diary details are private."
        body_html = "\n".join(
            [
                "<main>",
                "<h1>Diary</h1>",
                "<p>Diary details are private and are not available to crawlers.</p>",
                "</main>",
            ]
        )
        return _build_html_document(
            title=f"{title} · {site_title}" if site_title else title,
            description=description,
            canonical_url=canonical_url,
            site_name=site_title,
            body_html=body_html,
            json_ld=None,
            image=str(identity["image"]),
            author=real_name,
            app_shell_html=app_shell_html,
            shell_key=str(config["detail_shell_key"]),
        )

    item = _content_entry(session, config, slug)
    title = _content_entry_title(item)
    description = _content_entry_summary(item)
    canonical_url = _content_entry_url(base_url, config, slug)
    published_at = _content_entry_timestamp(item, "published_at") or _content_entry_timestamp(item, "created_at")
    updated_at = _content_entry_timestamp(item, "updated_at")
    tags = getattr(item, "tags", []) if isinstance(getattr(item, "tags", []), list) else []
    schema_type = str(config["schema_type"])

    json_ld = _compact_json_ld(
        {
            "@context": "https://schema.org",
            "@type": schema_type,
            "@id": f"{canonical_url}#article",
            "headline": title,
            "description": description,
            "url": canonical_url,
            "mainEntityOfPage": canonical_url,
            "datePublished": published_at.isoformat() if published_at else "",
            "dateModified": updated_at.isoformat() if updated_at else "",
            "author": {"@id": f"{base_url}/#person", "name": real_name},
            "publisher": {"@id": f"{base_url}/#website"},
            "keywords": tags,
            "articleBody": _plain_text(getattr(item, "body", ""), max_length=12000),
        }
    )

    body_html = "\n".join(
        [
            "<main>",
            _render_content_entry_html(
                item,
                base_url=base_url,
                config=config,
                heading_level=1,
                include_body=True,
            ),
            "</main>",
        ]
    )

    return _build_html_document(
        title=f"{title} · {site_title}" if site_title else title,
        description=description,
        canonical_url=canonical_url,
        site_name=site_title,
        body_html=body_html,
        json_ld=json_ld,
        og_type="article",
        image=str(identity["image"]),
        author=real_name,
        keywords=[str(tag) for tag in tags],
        app_shell_html=app_shell_html,
        shell_key=str(config["detail_shell_key"]),
        alternate_links=[
            ("application/rss+xml", _internal_url(base_url, str(config["feed_path"])), f"{config['title']} RSS"),
        ],
    )


def _social_page_copy(
    session: Session, page_key: str, fallback_title: str, fallback_description: str
) -> tuple[str, str]:
    page = session.scalar(select(PageCopy).where(PageCopy.page_key == page_key).limit(1))
    title = _clean_llms_text(page.title if page else "", max_length=160) or fallback_title
    description = _clean_llms_text(page.subtitle if page else "", max_length=260) or fallback_description
    return title, description


def _active_friends(session: Session) -> list[Friend]:
    return list(
        session.scalars(
            select(Friend)
            .where(Friend.status == "active")
            .order_by(Friend.order_index.asc(), Friend.created_at.asc())
            .limit(100)
        ).all()
    )


def _recent_friend_feed_items(session: Session) -> list[tuple[FriendFeedItem, Friend]]:
    return list(
        session.execute(
            select(FriendFeedItem, Friend)
            .join(FriendFeedSource, FriendFeedItem.source_id == FriendFeedSource.id)
            .join(Friend, FriendFeedSource.friend_id == Friend.id)
            .where(Friend.status == "active", FriendFeedSource.is_enabled.is_(True))
            .order_by(FriendFeedItem.published_at.desc(), FriendFeedItem.created_at.desc())
            .limit(30)
        ).all()
    )


def _render_friends_html(friends: list[Friend]) -> str:
    if not friends:
        return "<p>No public friend links are available.</p>"
    items = []
    for friend in friends:
        description = _clean_llms_text(friend.description, max_length=220)
        items.append(
            "\n".join(
                [
                    "<li>",
                    f'<h2><a href="{_html_attr(friend.url)}">{_html_text(friend.name)}</a></h2>',
                    f"<p>{_html_text(description)}</p>" if description else "",
                    "</li>",
                ]
            )
        )
    return "\n".join(["<section>", "<h2>Friend links</h2>", "<ol>", *items, "</ol>", "</section>"])


def _render_friend_feed_html(feed_items: list[tuple[FriendFeedItem, Friend]]) -> str:
    if not feed_items:
        return ""
    items = []
    for item, friend in feed_items:
        published_at = item.published_at
        published_html = ""
        if published_at:
            published_html = (
                f'<time datetime="{_html_attr(published_at.isoformat())}">'
                f"{_html_text(published_at.strftime('%Y-%m-%d'))}</time>"
            )
        summary = _clean_llms_text(item.summary, max_length=240)
        items.append(
            "\n".join(
                [
                    "<li>",
                    f'<h3><a href="{_html_attr(item.url)}">{_html_text(item.title)}</a></h3>',
                    f"<p>Source: {_html_text(friend.name)}{f' · {published_html}' if published_html else ''}</p>",
                    f"<p>{_html_text(summary)}</p>" if summary else "",
                    "</li>",
                ]
            )
        )
    return "\n".join(["<section>", "<h2>Recent friend-circle entries</h2>", "<ol>", *items, "</ol>", "</section>"])


def build_friends_seo_html(
    session: Session,
    site_url: str,
    *,
    app_shell_html: str | None = None,
) -> str:
    """Build crawler-readable HTML for the public friends page."""
    identity = _read_public_identity(session, site_url)
    base_url = str(identity["base_url"])
    site_title = str(identity["site_title"])
    real_name = str(identity["real_name"])
    page_title, page_description = _social_page_copy(
        session,
        "friends",
        "Friends",
        "Public friend links and recent friend-circle updates.",
    )
    canonical_url = _internal_url(base_url, "/friends")
    friends = _active_friends(session)
    feed_items = _recent_friend_feed_items(session)

    friend_items = [
        {
            "@type": "ListItem",
            "position": index,
            "url": friend.url,
            "item": _compact_json_ld(
                {
                    "@type": "WebSite",
                    "name": friend.name,
                    "url": friend.url,
                    "description": _clean_llms_text(friend.description, max_length=240),
                }
            ),
        }
        for index, friend in enumerate(friends, start=1)
    ]
    json_ld = _compact_json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "@id": f"{canonical_url}#page",
                    "url": canonical_url,
                    "name": page_title,
                    "description": page_description,
                    "isPartOf": {"@id": f"{base_url}/#website"},
                    "publisher": {"@id": f"{base_url}/#person"},
                    "mainEntity": {"@id": f"{canonical_url}#friends"},
                },
                {
                    "@type": "ItemList",
                    "@id": f"{canonical_url}#friends",
                    "name": "Friend links",
                    "numberOfItems": len(friends),
                    "itemListElement": friend_items,
                },
            ],
        }
    )
    body_html = "\n".join(
        [
            "<main>",
            f"<h1>{_html_text(page_title)}</h1>",
            f"<p>{_html_text(page_description)}</p>",
            _render_friends_html(friends),
            _render_friend_feed_html(feed_items),
            "</main>",
        ]
    )
    return _build_html_document(
        title=f"{page_title} · {site_title}" if site_title else page_title,
        description=page_description,
        canonical_url=canonical_url,
        site_name=site_title,
        body_html=body_html,
        json_ld=json_ld,
        image=str(identity["image"]),
        author=real_name,
        keywords=list(identity["keywords"]) if isinstance(identity["keywords"], list) else [],
        app_shell_html=app_shell_html,
        shell_key="friends",
    )


def _render_guestbook_entries_html(entries: list[object]) -> str:
    if not entries:
        return "<p>No public guestbook entries are available.</p>"
    items = []
    for entry in entries:
        created_at = getattr(entry, "created_at", None)
        created_html = ""
        if isinstance(created_at, datetime):
            created_html = (
                f'<time datetime="{_html_attr(created_at.isoformat())}">'
                f"{_html_text(created_at.strftime('%Y-%m-%d'))}</time>"
            )
        website = _clean_llms_text(getattr(entry, "website", ""), max_length=500)
        author = _clean_llms_text(getattr(entry, "name", ""), max_length=160) or "Visitor"
        body = _plain_text(getattr(entry, "body", ""), max_length=1200)
        author_html = f'<a href="{_html_attr(website)}">{_html_text(author)}</a>' if website else _html_text(author)
        items.append(
            "\n".join(
                [
                    f'<li id="guestbook-{_html_attr(getattr(entry, "id", ""))}">',
                    f"<h2>{author_html}</h2>",
                    f"<p>{created_html}</p>" if created_html else "",
                    f"<blockquote>{_html_text(body)}</blockquote>",
                    "</li>",
                ]
            )
        )
    return "\n".join(["<section>", "<h2>Guestbook entries</h2>", "<ol>", *items, "</ol>", "</section>"])


def build_guestbook_seo_html(
    session: Session,
    site_url: str,
    *,
    app_shell_html: str | None = None,
) -> str:
    """Build crawler-readable HTML for the public guestbook page."""
    identity = _read_public_identity(session, site_url)
    base_url = str(identity["base_url"])
    site_title = str(identity["site_title"])
    real_name = str(identity["real_name"])
    page_title, page_description = _social_page_copy(
        session,
        "guestbook",
        "Guestbook",
        "Public guestbook entries left by visitors.",
    )
    canonical_url = _internal_url(base_url, "/guestbook")
    entries = list_public_guestbook_entries(session, page=1, page_size=80).items

    entry_items = []
    for index, entry in enumerate(entries, start=1):
        entry_url = f"{canonical_url}#guestbook-{entry.id}"
        entry_items.append(
            {
                "@type": "ListItem",
                "position": index,
                "url": entry_url,
                "item": _compact_json_ld(
                    {
                        "@type": "Comment",
                        "url": entry_url,
                        "text": _plain_text(entry.body, max_length=1200),
                        "dateCreated": entry.created_at.isoformat(),
                        "author": {"@type": "Person", "name": entry.name},
                    }
                ),
            }
        )

    json_ld = _compact_json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "@id": f"{canonical_url}#page",
                    "url": canonical_url,
                    "name": page_title,
                    "description": page_description,
                    "isPartOf": {"@id": f"{base_url}/#website"},
                    "publisher": {"@id": f"{base_url}/#person"},
                    "mainEntity": {"@id": f"{canonical_url}#entries"},
                },
                {
                    "@type": "ItemList",
                    "@id": f"{canonical_url}#entries",
                    "name": "Guestbook entries",
                    "numberOfItems": len(entries),
                    "itemListElement": entry_items,
                },
            ],
        }
    )
    body_html = "\n".join(
        [
            "<main>",
            f"<h1>{_html_text(page_title)}</h1>",
            f"<p>{_html_text(page_description)}</p>",
            _render_guestbook_entries_html(list(entries)),
            "</main>",
        ]
    )
    return _build_html_document(
        title=f"{page_title} · {site_title}" if site_title else page_title,
        description=page_description,
        canonical_url=canonical_url,
        site_name=site_title,
        body_html=body_html,
        json_ld=json_ld,
        image=str(identity["image"]),
        author=real_name,
        keywords=list(identity["keywords"]) if isinstance(identity["keywords"], list) else [],
        app_shell_html=app_shell_html,
        shell_key="guestbook",
    )


def _build_html_document(
    *,
    title: str,
    description: str,
    canonical_url: str,
    site_name: str,
    body_html: str,
    json_ld: object,
    og_type: str = "website",
    image: str = "",
    author: str = "",
    share_title: str = "",
    keywords: list[str] | None = None,
    alternate_links: list[tuple[str, str, str]] | None = None,
    app_shell_html: str | None = None,
    shell_key: str = "page",
) -> str:
    keyword_content = ", ".join(keywords or [])
    social_title = share_title or title
    head_markup_parts = [
        f"<title>{_html_text(title)}</title>",
        f'<meta name="description" content="{_html_attr(description)}">',
        f'<meta name="title" content="{_html_attr(social_title)}">',
        '<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">',
        f'<link rel="canonical" href="{_html_attr(canonical_url)}">',
        f'<meta property="og:type" content="{_html_attr(og_type)}">',
        f'<meta property="og:title" content="{_html_attr(social_title)}">',
        f'<meta property="og:description" content="{_html_attr(description)}">',
        f'<meta property="og:url" content="{_html_attr(canonical_url)}">',
        f'<meta property="og:site_name" content="{_html_attr(site_name)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{_html_attr(social_title)}">',
        f'<meta name="twitter:description" content="{_html_attr(description)}">',
    ]
    if author:
        head_markup_parts.append(f'<meta name="author" content="{_html_attr(author)}">')
    if keyword_content:
        head_markup_parts.append(f'<meta name="keywords" content="{_html_attr(keyword_content)}">')
    if image:
        head_markup_parts.extend(
            [
                f'<meta property="og:image" content="{_html_attr(image)}">',
                f'<meta name="twitter:image" content="{_html_attr(image)}">',
            ]
        )
    for rel_type, href, link_title in alternate_links or []:
        head_markup_parts.append(
            f'<link rel="alternate" type="{_html_attr(rel_type)}" href="{_html_attr(href)}" title="{_html_attr(link_title)}">'
        )
    head_markup_parts.append(_json_ld_script(json_ld))
    head_markup = "\n".join(head_markup_parts)
    if app_shell_html:
        return _inject_seo_app_shell(
            app_shell_html, head_markup=head_markup, fallback_html=body_html, shell_key=shell_key
        )

    head_parts = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        head_markup,
        "</head>",
        "<body>",
        body_html,
        "</body>",
        "</html>",
    ]
    return "\n".join(head_parts) + "\n"


def _strip_loading_head_tags(app_shell_html: str) -> str:
    patterns = [
        r"\s*<title>.*?</title>",
        r'\s*<meta\s+name=["\']description["\'][^>]*>',
        r'\s*<meta\s+name=["\']title["\'][^>]*>',
        r'\s*<meta\s+name=["\']author["\'][^>]*>',
        r'\s*<meta\s+name=["\']robots["\'][^>]*>',
        r'\s*<link\s+rel=["\']canonical["\'][^>]*>',
        r'\s*<meta\s+property=["\']og:(?:title|description|type|site_name|image)["\'][^>]*>',
        r'\s*<meta\s+name=["\']twitter:(?:card|title|description|image)["\'][^>]*>',
    ]
    next_html = app_shell_html
    for pattern in patterns:
        next_html = re.sub(pattern, "", next_html, flags=re.IGNORECASE | re.DOTALL)
    return next_html


def _inject_seo_app_shell(
    app_shell_html: str,
    *,
    head_markup: str,
    fallback_html: str,
    shell_key: str,
) -> str:
    html = _strip_loading_head_tags(app_shell_html or _DEFAULT_APP_SHELL_HTML)
    noscript = f'<noscript data-seo-shell="{_html_attr(shell_key)}">\n{fallback_html}\n</noscript>'
    html = html.replace("</body>", f"{noscript}\n</body>", 1) if "</body>" in html else f"{html}\n{noscript}"

    if "</head>" in html:
        html = html.replace("</head>", f"{head_markup}\n</head>", 1)
    else:
        html = f'<!doctype html>\n<html lang="zh-CN">\n<head>\n{head_markup}\n</head>\n<body>\n{html}\n</body>\n</html>'

    return html if html.endswith("\n") else f"{html}\n"


def build_home_seo_html(
    session: Session,
    site_url: str,
    *,
    api_base_path: str = "/api",
    app_shell_html: str | None = None,
) -> str:
    """Build no-JS homepage HTML for crawlers that do not render the SPA."""
    identity = _read_public_identity(session, site_url)
    base_url = str(identity["base_url"])
    profile = identity["profile"]
    real_name = str(identity["real_name"])
    site_title = str(identity["site_title"])
    search_title = str(identity["search_title"])
    nickname = str(identity["nickname"])
    description = str(identity["search_description"])
    identity_summary = str(identity["identity_summary"])
    identity_bridge_sentence = str(identity["identity_bridge_sentence"])
    expertise = list(identity["expertise"]) if isinstance(identity["expertise"], list) else []
    same_as = list(identity["same_as"]) if isinstance(identity["same_as"], list) else []
    keywords = list(identity["keywords"]) if isinstance(identity["keywords"], list) else []
    role = _clean_llms_text(profile.role if isinstance(profile, SiteProfile) else "", max_length=160)
    person_id = f"{base_url}/#person"
    website_id = f"{base_url}/#website"
    include_diary = not diary_private_enabled(session)
    alternate_links = [
        ("text/markdown", _internal_url(base_url, "/llms.txt"), "AI-readable site guide"),
        ("application/rss+xml", _internal_url(base_url, "/feeds/posts.xml"), "Latest public posts"),
    ]
    if include_diary:
        alternate_links.append(
            ("application/rss+xml", _internal_url(base_url, "/feeds/diary.xml"), "Latest public diary entries")
        )

    json_ld = _compact_json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Person",
                    "@id": person_id,
                    "name": real_name,
                    "alternateName": [nickname] if nickname and nickname != real_name else [],
                    "jobTitle": role,
                    "description": identity_summary,
                    "url": _internal_url(base_url, "/"),
                    "image": identity["image"],
                    "sameAs": same_as,
                    "knowsAbout": expertise,
                    "mainEntityOfPage": {"@id": f"{base_url}/resume#profile"},
                },
                {
                    "@type": "WebSite",
                    "@id": website_id,
                    "name": site_title,
                    "alternateName": search_title if search_title and search_title != site_title else "",
                    "url": _internal_url(base_url, "/"),
                    "description": description,
                    "publisher": {"@id": person_id},
                    "about": {"@id": person_id},
                    "mainEntity": {"@id": person_id},
                },
            ],
        }
    )

    expertise_html = ""
    if expertise:
        expertise_items = "".join(f"<li>{_html_text(item)}</li>" for item in expertise[:16])
        expertise_html = "\n".join(["<section>", "<h2>Expertise</h2>", f"<ul>{expertise_items}</ul>", "</section>"])

    body_html = "\n".join(
        [
            "<main>",
            f"<h1>{_html_text(site_title)}</h1>",
            f"<p>{_html_text(identity_bridge_sentence)}</p>" if identity_bridge_sentence else "",
            f"<p>{_html_text(identity_summary)}</p>",
            f'<p>Public identity: <a href="{_html_attr(_internal_url(base_url, "/resume"))}">{_html_text(real_name)}</a></p>',
            _render_ai_navigation_instructions(base_url, include_diary=include_diary),
            _render_public_resource_links(base_url, api_base_path=api_base_path, include_diary=include_diary),
            expertise_html,
            _render_posts_list(session, base_url),
            "</main>",
        ]
    )

    return _build_html_document(
        title=site_title,
        description=description,
        canonical_url=_internal_url(base_url, "/"),
        site_name=site_title,
        body_html=body_html,
        json_ld=json_ld,
        image=str(identity["image"]),
        author=real_name,
        share_title=search_title or site_title,
        keywords=keywords,
        app_shell_html=app_shell_html,
        shell_key="home",
        alternate_links=alternate_links,
    )


def build_resume_seo_html(
    session: Session,
    site_url: str,
    *,
    api_base_path: str = "/api",
    app_shell_html: str | None = None,
) -> str:
    """Build no-JS resume HTML for crawlers that do not render the SPA."""
    identity = _read_public_identity(session, site_url)
    base_url = str(identity["base_url"])
    resume = identity["resume"]
    if not isinstance(resume, ResumeBasics):
        raise ResourceNotFound("resume basics are missing")

    real_name = str(identity["real_name"])
    site_title = str(identity["site_title"])
    nickname = str(identity["nickname"])
    description = _plain_text(resume.summary, max_length=280) or str(identity["search_description"])
    description = _strengthen_identity_description(
        description,
        real_name=real_name,
        nickname=nickname,
        max_length=280,
    )
    expertise = list(identity["expertise"]) if isinstance(identity["expertise"], list) else []
    same_as = list(identity["same_as"]) if isinstance(identity["same_as"], list) else []
    api_path = _normalize_robots_path(api_base_path, "/api").rstrip("/")
    profile_page_id = f"{base_url}/resume#profile"
    person_id = f"{base_url}/#person"
    include_diary = not diary_private_enabled(session)

    json_ld = _compact_json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "ProfilePage",
                    "@id": profile_page_id,
                    "url": _internal_url(base_url, "/resume"),
                    "name": f"{real_name} Resume",
                    "description": description,
                    "about": {"@id": person_id},
                    "mainEntity": {"@id": person_id},
                    "isPartOf": {"@id": f"{base_url}/#website"},
                },
                {
                    "@type": "Person",
                    "@id": person_id,
                    "name": real_name,
                    "alternateName": [nickname] if nickname and nickname != real_name else [],
                    "description": str(identity["identity_summary"]),
                    "url": _internal_url(base_url, "/"),
                    "image": identity["image"],
                    "sameAs": same_as,
                    "knowsAbout": expertise,
                },
            ],
        }
    )

    contact_items = []
    if resume.location:
        contact_items.append(f"<li>Location: {_html_text(resume.location)}</li>")
    if resume.email:
        contact_items.append(
            f'<li>Email: <a href="mailto:{_html_attr(resume.email)}">{_html_text(resume.email)}</a></li>'
        )
    contact_html = f"<section><h2>Contact</h2><ul>{''.join(contact_items)}</ul></section>" if contact_items else ""
    body_html = "\n".join(
        [
            "<main>",
            f"<h1>{_html_text(real_name)}</h1>",
            f'<p><a href="{_html_attr(_internal_url(base_url, "/resume.md"))}">AI-readable resume Markdown</a></p>',
            f'<p><a href="{_html_attr(_internal_url(base_url, f"{api_path}/v1/site/resume"))}">Structured resume JSON</a></p>',
            contact_html,
            "<section>",
            "<h2>Resume</h2>",
            _render_markdownish_html(resume.summary),
            "</section>",
            _render_public_resource_links(base_url, api_base_path=api_base_path, include_diary=include_diary),
            "</main>",
        ]
    )

    browser_title = real_name
    share_title = (
        f"{real_name} Resume · {site_title}" if site_title and site_title != real_name else f"{real_name} Resume"
    )

    return _build_html_document(
        title=browser_title,
        description=description,
        canonical_url=_internal_url(base_url, "/resume"),
        site_name=site_title,
        body_html=body_html,
        json_ld=json_ld,
        og_type="profile",
        image=str(identity["image"]),
        author=real_name,
        share_title=share_title,
        keywords=list(identity["keywords"]) if isinstance(identity["keywords"], list) else [],
        app_shell_html=app_shell_html,
        shell_key="resume",
        alternate_links=[
            ("text/markdown", _internal_url(base_url, "/resume.md"), "AI-readable resume"),
            ("application/json", _internal_url(base_url, f"{api_path}/v1/site/resume"), "Structured resume JSON"),
        ],
    )


def build_resume_markdown(session: Session) -> str:
    """Build a no-JS Markdown resume for AI readers and simple HTTP clients."""
    resume = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
    if resume is None:
        raise ResourceNotFound("resume basics are missing")

    title = _clean_llms_text(resume.title, max_length=160) or "Resume"
    summary = str(resume.summary or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [f"# {title}", ""]
    contact_lines = []
    if resume.location:
        contact_lines.append(f"- Location: {_clean_llms_text(resume.location, max_length=160)}")
    if resume.email:
        contact_lines.append(f"- Email: {_clean_llms_text(resume.email, max_length=160)}")
    if resume.profile_image_url:
        contact_lines.append(f"- Profile image: {_clean_llms_text(resume.profile_image_url, max_length=500)}")

    if contact_lines:
        lines.extend(["## Contact", "", *contact_lines, ""])

    lines.extend(["## Summary", "", summary or "No public resume summary is available."])
    return "\n".join(lines).strip() + "\n"


def build_llms_txt(session: Session, site_url: str, *, api_base_path: str = "/api") -> str:
    """Build an AI-readable site map for agents that cannot execute the SPA."""
    base_url = site_url.rstrip("/")
    api_path = _normalize_robots_path(api_base_path, "/api").rstrip("/")
    include_diary = not diary_private_enabled(session)
    profile = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    resume = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
    social_links = session.scalars(
        select(SocialLink).order_by(SocialLink.order_index.asc(), SocialLink.created_at.asc()).limit(8)
    ).all()
    search_config = _read_search_optimization(profile)
    real_name = (
        _clean_llms_text(search_config.get("real_name"), max_length=120)
        or _clean_llms_text(resume.title if resume else "", max_length=120)
        or _clean_llms_text(profile.name if profile else "", max_length=120)
        or "Site owner"
    )
    site_title = (
        _clean_llms_text(search_config.get("meta_title"), max_length=160)
        or _clean_llms_text(profile.title if profile else "", max_length=160)
        or real_name
    )
    identity_summary = (
        _clean_llms_text(search_config.get("llm_summary"), max_length=360)
        or _clean_llms_text(search_config.get("meta_description"), max_length=360)
        or _clean_llms_text(profile.bio if profile else "", max_length=360)
        or _clean_llms_text(resume.summary if resume else "", max_length=360)
        or f"Public personal website and blog for {real_name}."
    )
    expertise = _read_text_list(search_config.get("expertise"))

    writing_guidance = (
        "For public writing, read /posts and /diary first; they are crawler-readable index pages with summaries and canonical links."
        if include_diary
        else "For public writing, read /posts first; diary details are private and not part of the public AI-readable surface."
    )
    detail_guidance = (
        "Strongly recommended: open every public /posts/{slug} and /diary/{slug} detail page in the order shown on /posts and /diary before summarizing the person's writing."
        if include_diary
        else "Strongly recommended: open every public /posts/{slug} detail page in the order shown on /posts before summarizing the person's writing."
    )

    lines = [
        f"# {site_title}",
        "",
        f"> {identity_summary}",
        "",
        f"This is the public AI-readable map for {real_name}.",
        "The site is a personal blog, resume, and writing platform.",
        "To understand the person behind the site, read /resume.md first. If structured data is needed, use /api/v1/site/resume.",
        writing_guidance,
        detail_guidance,
        "Use RSS feeds as update signals, not as the primary source of full content.",
        "If your browser cannot execute JavaScript, prefer the crawler-readable public pages and machine-readable endpoints listed below because the visual frontend is a client-rendered SPA.",
        "The admin interface and admin APIs are intentionally out of scope.",
    ]
    if not include_diary:
        lines.append(
            "Do not access /diary or /diary/*; diary details are private unless the site owner grants explicit permission through the logged-in web UI."
        )

    if profile and profile.role:
        lines.append(f"Public role line: {_clean_llms_text(profile.role, max_length=180)}.")
    if expertise:
        lines.append(f"Expertise topics: {', '.join(expertise[:12])}.")

    machine_links = [
        f"- [Public bootstrap JSON]({_internal_url(base_url, f'{api_path}/v1/site/bootstrap')}): Site profile, navigation, page metadata, and resume in one read-only JSON payload.",
        f"- [Resume JSON]({_internal_url(base_url, f'{api_path}/v1/site/resume')}): Structured public resume data.",
        f"- [Posts JSON]({_internal_url(base_url, f'{api_path}/v1/site/posts')}): Public article list with titles and summaries.",
        f"- [Posts RSS]({_internal_url(base_url, '/feeds/posts.xml')}): Update feed for public long-form posts; use /posts and /posts/{{slug}} for crawler-readable content.",
        f"- [Thoughts RSS]({_internal_url(base_url, '/feeds/thoughts.xml')}): Update feed for public short notes; use /thoughts for crawler-readable content.",
        f"- [Excerpts RSS]({_internal_url(base_url, '/feeds/excerpts.xml')}): Update feed for public excerpts; use /excerpts for crawler-readable content.",
    ]
    public_pages = [
        f"- [Resume page]({_internal_url(base_url, '/resume')}): Browser-rendered resume page; use /resume.md or resume JSON when JavaScript is unavailable.",
        f"- [Posts]({_internal_url(base_url, '/posts')}): Crawler-readable long-form article index with summaries and canonical detail links.",
        f"- [Thoughts]({_internal_url(base_url, '/thoughts')}): Crawler-readable short notes; entries are available directly on this page.",
        f"- [Excerpts]({_internal_url(base_url, '/excerpts')}): Crawler-readable excerpts and reading notes; entries are available directly on this page.",
    ]
    if include_diary:
        machine_links.insert(
            3,
            f"- [Diary JSON]({_internal_url(base_url, f'{api_path}/v1/site/diary')}): Public diary list, if available.",
        )
        machine_links.insert(
            6,
            f"- [Diary RSS]({_internal_url(base_url, '/feeds/diary.xml')}): Update feed for public diary entries; use /diary and /diary/{{slug}} for crawler-readable content.",
        )
        public_pages.insert(
            3,
            f"- [Diary]({_internal_url(base_url, '/diary')}): Crawler-readable diary index with summaries and canonical detail links.",
        )

    lines.extend(
        [
            "",
            "## Start here",
            "",
            f"- [Resume Markdown]({_internal_url(base_url, '/resume.md')}): Public CV/resume for {real_name}; read this first for identity, education, projects, skills, and contact context.",
            f"- [Homepage]({_internal_url(base_url, '/')}): Main public profile page, visual identity, navigation, and primary links.",
            f"- [Sitemap]({_internal_url(base_url, '/sitemap.xml')}): Complete public URL index for crawlable pages.",
            f"- [Robots policy]({_internal_url(base_url, '/robots.txt')}): Crawler access policy; admin routes are not for indexing or AI browsing.",
            "",
            "## Machine-readable public data",
            "",
            *machine_links,
            "",
            "## Public pages",
            "",
            *public_pages,
        ]
    )

    posts = session.scalars(
        select(PostEntry)
        .where(PostEntry.visibility == "public")
        .order_by(PostEntry.is_pinned.desc(), PostEntry.pin_order.asc(), PostEntry.updated_at.desc())
        .limit(8)
    ).all()
    if posts:
        lines.extend(["", "## Representative posts", ""])
        for post in posts:
            title = _markdown_label(post.public_title or post.title, "Untitled post")
            note = _markdown_note(post.summary or post.body)
            suffix = f": {note}" if note else ""
            lines.append(f"- [{title}]({_internal_url(base_url, f'/posts/{post.slug}')}){suffix}")

    if social_links:
        lines.extend(["", "## Identity links", ""])
        for link in social_links:
            label = _markdown_label(link.name, "Public profile")
            lines.append(f"- [{label}]({_public_link(base_url, link.href)}): Public identity or contact link.")

    lines.extend(
        [
            "",
            "## Optional",
            "",
            f"- [Friends]({_internal_url(base_url, '/friends')}): Public friends/blogroll page.",
            f"- [Guestbook]({_internal_url(base_url, '/guestbook')}): Public guestbook.",
            f"- [Calendar]({_internal_url(base_url, '/calendar')}): Public activity calendar.",
        ]
    )

    return "\n".join(lines).strip() + "\n"

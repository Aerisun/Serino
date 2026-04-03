from __future__ import annotations

import json
import random
import socket
from collections import deque
from copy import deepcopy
from html.parser import HTMLParser
from ipaddress import ip_address
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.site_config import repository as repo
from aerisun.domain.site_config.schemas import (
    CommunityConfigAdminRead,
    CommunityConfigRead,
    LinkPreviewRead,
    NavChildRead,
    NavItemAdminRead,
    NavItemRead,
    PageCollectionRead,
    PageCopyRead,
    PoemRead,
    ResumeRead,
    SiteConfigRead,
    SitePoemPreviewRead,
    SiteProfileAdminRead,
    SiteProfileRead,
    SocialLinkRead,
)
from aerisun.domain.waline.service import sync_admin_comment_profile

DEFAULT_HITOKOTO_TYPES = ["d", "i"]
HITOKOTO_ENDPOINT = "https://v1.hitokoto.cn/"
HITOKOTO_RETRY_COUNT = 8
HITOKOTO_TIMEOUT = 5.0
HITOKOTO_REQUESTS_PER_SECOND = 2
HITOKOTO_REQUEST_INTERVAL_SECONDS = 1 / HITOKOTO_REQUESTS_PER_SECOND
HITOKOTO_CACHE_SIZE = 20
HITOKOTO_CACHE_REFILL_THRESHOLD = 15
LINK_PREVIEW_TIMEOUT = 6.0
LINK_PREVIEW_CACHE_TTL_SECONDS = 900.0
LINK_PREVIEW_MAX_BYTES = 512 * 1024
LINK_PREVIEW_MAX_REDIRECTS = 4
LINK_PREVIEW_IMAGE_MAX_BYTES = 5 * 1024 * 1024
LINK_PREVIEW_USER_AGENT = "Mozilla/5.0 (compatible; AerisunLinkPreview/1.0; +https://aerisun.example)"
INTERNAL_SITE_FEATURE_FLAGS = {
    "agent_model_config",
    "agent_workflows",
    "agent_workflow_draft",
    "agent_surface_drafts",
    "mcp_public_access",
}

HitokotoCacheKey = tuple[tuple[str, ...], tuple[str, ...]]

# Keep a small per-settings buffer so refreshes can render immediately.
_HITOKOTO_CACHE: dict[HitokotoCacheKey, deque[SitePoemPreviewRead]] = {}
_HITOKOTO_CACHE_REFRESHING: set[HitokotoCacheKey] = set()
_HITOKOTO_CACHE_LOCK = Lock()
_HITOKOTO_REQUEST_LOCK = Lock()
_HITOKOTO_NEXT_REQUEST_AT = 0.0
_LINK_PREVIEW_CACHE: dict[str, tuple[float, LinkPreviewRead]] = {}
_LINK_PREVIEW_CACHE_LOCK = Lock()


class _LinkPreviewHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.icon_href: str | None = None
        self.canonical_href: str | None = None
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "").strip() for key, value in attrs}
        tag_name = tag.lower()

        if tag_name == "title":
            self._in_title = True
            return

        if tag_name == "meta":
            key = attributes.get("property") or attributes.get("name")
            content = attributes.get("content", "").strip()
            if key and content:
                normalized_key = key.lower()
                self.meta.setdefault(normalized_key, content)
            return

        if tag_name == "link":
            rel_tokens = {item.strip().lower() for item in attributes.get("rel", "").split() if item.strip()}
            href = attributes.get("href", "").strip()
            if href and self.canonical_href is None and "canonical" in rel_tokens:
                self.canonical_href = href
            if (
                href
                and self.icon_href is None
                and rel_tokens.intersection({"icon", "shortcut", "shortcut icon", "apple-touch-icon", "mask-icon"})
            ):
                self.icon_href = href

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            stripped = data.strip()
            if stripped:
                self._title_parts.append(stripped)

    @property
    def title(self) -> str | None:
        if not self._title_parts:
            return None
        return " ".join(self._title_parts).strip() or None


def _public_feature_flags(raw_flags: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(raw_flags or {})
    public_flags: dict[str, Any] = {}
    for key, value in source.items():
        normalized = str(key or "").strip()
        if not normalized:
            continue
        if normalized in INTERNAL_SITE_FEATURE_FLAGS or normalized.startswith("agent_"):
            continue
        public_flags[normalized] = deepcopy(value)
    return public_flags


def _normalize_link_preview_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        raise ValidationError("链接不能为空。")

    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"}:
        raise ValidationError("仅支持 http 或 https 链接预览。")
    if not parts.netloc:
        raise ValidationError("链接格式不正确。")
    if parts.username or parts.password:
        raise ValidationError("不支持包含认证信息的链接。")
    if parts.port not in {None, 80, 443}:
        raise ValidationError("仅支持标准端口的公开链接。")

    normalized = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    return normalized


def _is_public_ip_text(value: str) -> bool:
    try:
        return ip_address(value).is_global
    except ValueError:
        return False


def _ensure_public_link_preview_url(url: str) -> str:
    normalized = _normalize_link_preview_url(url)
    parts = urlsplit(normalized)
    hostname = (parts.hostname or "").strip().lower()
    if not hostname:
        raise ValidationError("链接缺少主机名。")
    if hostname in {"localhost", "0.0.0.0"} or hostname.endswith(".local"):
        raise ValidationError("不支持本地或内网地址的链接预览。")

    if _is_public_ip_text(hostname):
        return normalized

    try:
        resolved = {
            item[4][0]
            for item in socket.getaddrinfo(
                hostname,
                parts.port or (443 if parts.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        raise ValidationError("链接主机名解析失败。") from exc

    if not resolved:
        raise ValidationError("链接主机名解析失败。")

    if any(not _is_public_ip_text(ip) for ip in resolved):
        raise ValidationError("不支持本地或内网地址的链接预览。")

    return normalized


def _trim_preview_text(value: str | None, *, limit: int) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _resolve_link_preview_asset(asset_url: str | None, *, base_url: str) -> str | None:
    value = str(asset_url or "").strip()
    if not value or value.startswith("data:"):
        return None
    return urljoin(base_url, value)


def _parse_positive_int(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _read_link_preview_body(response: httpx.Response) -> str:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > LINK_PREVIEW_MAX_BYTES:
            break
        chunks.append(chunk)

    payload = b"".join(chunks)
    encoding = response.encoding or "utf-8"
    return payload.decode(encoding, errors="replace")


def _fetch_link_preview_document(url: str) -> tuple[str, str, str]:
    headers = {
        "User-Agent": LINK_PREVIEW_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.2",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    current_url = url
    with httpx.Client(timeout=LINK_PREVIEW_TIMEOUT, follow_redirects=False, headers=headers) as client:
        for _ in range(LINK_PREVIEW_MAX_REDIRECTS + 1):
            with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "").strip()
                    if not location:
                        break
                    current_url = _ensure_public_link_preview_url(urljoin(str(response.url), location))
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                document = _read_link_preview_body(response)
                return str(response.url), content_type, document

    raise ValidationError("链接重定向次数过多。")


def _extract_link_preview(url: str) -> LinkPreviewRead:
    normalized_url = _ensure_public_link_preview_url(url)
    final_url = normalized_url

    try:
        final_url, content_type, document = _fetch_link_preview_document(normalized_url)
    except httpx.HTTPError as exc:
        hostname = urlsplit(normalized_url).hostname or ""
        return LinkPreviewRead(
            url=normalized_url,
            resolved_url=normalized_url,
            hostname=hostname,
            available=False,
            error=f"预览抓取失败：{exc.__class__.__name__}",
        )

    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        hostname = urlsplit(final_url).hostname or urlsplit(normalized_url).hostname or ""
        return LinkPreviewRead(
            url=normalized_url,
            resolved_url=final_url,
            hostname=hostname,
            site_name=hostname.replace("www.", "", 1),
            available=False,
            error="目标页面不是 HTML 文档。",
        )

    parser = _LinkPreviewHTMLParser()
    parser.feed(document)
    parser.close()

    meta = parser.meta
    resolved_url = (
        _resolve_link_preview_asset(meta.get("og:url") or parser.canonical_href, base_url=final_url) or final_url
    )
    hostname = urlsplit(resolved_url).hostname or urlsplit(final_url).hostname or ""
    title = _trim_preview_text(
        meta.get("og:title") or meta.get("twitter:title") or parser.title,
        limit=180,
    )
    description = _trim_preview_text(
        meta.get("og:description") or meta.get("twitter:description") or meta.get("description"),
        limit=320,
    )
    site_name = _trim_preview_text(meta.get("og:site_name"), limit=80) or hostname.replace("www.", "", 1)
    image_url = _resolve_link_preview_asset(
        meta.get("og:image") or meta.get("twitter:image") or meta.get("twitter:image:src"),
        base_url=final_url,
    )
    image_width = _parse_positive_int(meta.get("og:image:width") or meta.get("twitter:image:width"))
    image_height = _parse_positive_int(meta.get("og:image:height") or meta.get("twitter:image:height"))
    icon_url = _resolve_link_preview_asset(parser.icon_href, base_url=final_url)

    return LinkPreviewRead(
        url=normalized_url,
        resolved_url=resolved_url,
        hostname=hostname,
        title=title,
        description=description,
        site_name=site_name,
        image_url=image_url,
        image_width=image_width,
        image_height=image_height,
        icon_url=icon_url,
        available=bool(title or description or image_url or icon_url),
        error=None,
    )


def get_site_link_preview(url: str) -> LinkPreviewRead:
    normalized_url = _ensure_public_link_preview_url(url)
    now = monotonic()

    with _LINK_PREVIEW_CACHE_LOCK:
        cached = _LINK_PREVIEW_CACHE.get(normalized_url)
        if cached and cached[0] > now:
            return cached[1]

    preview = _extract_link_preview(normalized_url)

    with _LINK_PREVIEW_CACHE_LOCK:
        _LINK_PREVIEW_CACHE[normalized_url] = (now + LINK_PREVIEW_CACHE_TTL_SECONDS, preview)

    return preview


def fetch_site_link_preview_image(url: str) -> tuple[bytes, str]:
    normalized_url = _ensure_public_link_preview_url(url)
    headers = {
        "User-Agent": LINK_PREVIEW_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*;q=0.9,*/*;q=0.1",
        "Referer": normalized_url,
    }

    try:
        with httpx.Client(
            timeout=LINK_PREVIEW_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(normalized_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                raise ValidationError("目标资源不是可预览图片。")
            payload = response.content
            if len(payload) > LINK_PREVIEW_IMAGE_MAX_BYTES:
                raise ValidationError("预览图片过大，无法加载。")
            return payload, content_type
    except httpx.HTTPError as exc:
        raise ValidationError(f"预览图片抓取失败：{exc.__class__.__name__}") from exc


def _normalize_hitokoto_types(types: list[str]) -> list[str]:
    normalized = [item.strip() for item in types if item.strip()]
    return normalized or list(DEFAULT_HITOKOTO_TYPES)


def _build_hitokoto_attribution(payload: dict[str, object]) -> str | None:
    parts = [
        str(payload.get("from_who") or "").strip(),
        str(payload.get("from") or "").strip(),
    ]
    attribution = " · ".join(part for part in parts if part)
    return attribution or None


def _pick_custom_poem_content(poems: list) -> str:
    candidates = [str(poem.content or "").strip() for poem in poems if str(poem.content or "").strip()]
    return random.choice(candidates) if candidates else ""


def _wait_for_hitokoto_request_slot() -> None:
    global _HITOKOTO_NEXT_REQUEST_AT

    with _HITOKOTO_REQUEST_LOCK:
        now = monotonic()
        if now < _HITOKOTO_NEXT_REQUEST_AT:
            sleep(_HITOKOTO_NEXT_REQUEST_AT - now)
            now = monotonic()
        _HITOKOTO_NEXT_REQUEST_AT = now + HITOKOTO_REQUEST_INTERVAL_SECONDS


def _fetch_hitokoto_poem_with_client(
    client: httpx.Client,
    *,
    types: list[str],
) -> SitePoemPreviewRead:
    params = [("c", poem_type) for poem_type in types]

    for _ in range(HITOKOTO_RETRY_COUNT):
        _wait_for_hitokoto_request_slot()
        response = client.get(HITOKOTO_ENDPOINT, params=params)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValidationError("在线诗句返回格式不正确。")

        content = str(payload.get("hitokoto") or "").strip()
        if not content:
            continue
        return SitePoemPreviewRead(
            mode="hitokoto",
            content=content,
            attribution=_build_hitokoto_attribution(payload),
        )

    raise ValidationError("在线诗句暂时不可用，请稍后重试。")


def _build_hitokoto_cache_key(types: list[str]) -> HitokotoCacheKey:
    return tuple(types), ()


def _pop_cached_hitokoto_poem(cache_key: HitokotoCacheKey) -> tuple[SitePoemPreviewRead | None, int]:
    with _HITOKOTO_CACHE_LOCK:
        queue = _HITOKOTO_CACHE.get(cache_key)
        if not queue:
            return None, 0

        item = queue.popleft()
        remaining = len(queue)
        if not queue:
            _HITOKOTO_CACHE.pop(cache_key, None)
        return item, remaining


def _refill_hitokoto_cache(
    cache_key: HitokotoCacheKey,
    *,
    types: list[str],
    target_size: int = HITOKOTO_CACHE_SIZE,
) -> int:
    with _HITOKOTO_CACHE_LOCK:
        current_size = len(_HITOKOTO_CACHE.get(cache_key, ()))

    missing = max(target_size - current_size, 0)
    if missing == 0:
        return 0

    new_items: list[SitePoemPreviewRead] = []
    last_error: Exception | None = None

    with httpx.Client(timeout=HITOKOTO_TIMEOUT, follow_redirects=True) as client:
        for _ in range(missing):
            try:
                new_items.append(
                    _fetch_hitokoto_poem_with_client(
                        client,
                        types=types,
                    )
                )
            except (httpx.HTTPError, ValueError, ValidationError) as exc:
                last_error = exc
                break

    if new_items:
        with _HITOKOTO_CACHE_LOCK:
            queue = _HITOKOTO_CACHE.setdefault(cache_key, deque())
            available_slots = max(HITOKOTO_CACHE_SIZE - len(queue), 0)
            queue.extend(new_items[:available_slots])

    if not new_items and last_error is not None:
        raise last_error

    return len(new_items)


def _schedule_hitokoto_cache_refill(
    cache_key: HitokotoCacheKey,
    *,
    types: list[str],
) -> None:
    with _HITOKOTO_CACHE_LOCK:
        if cache_key in _HITOKOTO_CACHE_REFRESHING:
            return
        if len(_HITOKOTO_CACHE.get(cache_key, ())) >= HITOKOTO_CACHE_SIZE:
            return
        _HITOKOTO_CACHE_REFRESHING.add(cache_key)

    def _worker() -> None:
        try:
            _refill_hitokoto_cache(
                cache_key,
                types=types,
                target_size=HITOKOTO_CACHE_SIZE,
            )
        except (httpx.HTTPError, ValueError, ValidationError):
            pass
        finally:
            with _HITOKOTO_CACHE_LOCK:
                _HITOKOTO_CACHE_REFRESHING.discard(cache_key)

    Thread(target=_worker, daemon=True).start()


def _get_cached_hitokoto_poem(types: list[str]) -> SitePoemPreviewRead:
    normalized_types = _normalize_hitokoto_types(types)
    cache_key = _build_hitokoto_cache_key(normalized_types)

    poem, remaining = _pop_cached_hitokoto_poem(cache_key)
    if poem is None:
        _refill_hitokoto_cache(
            cache_key,
            types=normalized_types,
            target_size=HITOKOTO_CACHE_SIZE,
        )
        poem, remaining = _pop_cached_hitokoto_poem(cache_key)

    if poem is None:
        raise ValidationError("在线诗句获取失败，请稍后重试。")

    if remaining <= HITOKOTO_CACHE_REFILL_THRESHOLD:
        _schedule_hitokoto_cache_refill(
            cache_key,
            types=normalized_types,
        )

    return poem


def get_site_config(session: Session) -> SiteConfigRead:
    site = repo.find_site_profile(session)
    if site is None:
        raise ResourceNotFound("site profile is missing")

    links = repo.find_social_links(session, site.id)
    poems = repo.find_poems(session, site.id)

    hero_actions = json.loads(site.hero_actions) if site.hero_actions else []
    feature_flags = _public_feature_flags(site.feature_flags)

    from aerisun.domain.subscription.service import subscription_enabled

    feature_flags["content_subscription"] = subscription_enabled(session)

    nav_items = repo.find_enabled_nav_items(session, site.id)

    children_map: dict[str, list] = {}
    for item in nav_items:
        if item.parent_id:
            children_map.setdefault(item.parent_id, []).append(item)

    navigation = []
    for item in nav_items:
        if item.parent_id is None:
            nav_read = NavItemRead(
                label=item.label,
                trigger=item.trigger,
                href=item.href,
                children=[
                    NavChildRead(label=child.label, href=child.href or "") for child in children_map.get(item.id, [])
                ],
            )
            navigation.append(nav_read)

    return SiteConfigRead(
        site=SiteProfileRead(
            name=site.name,
            title=site.title,
            bio=site.bio,
            role=site.role,
            og_image=site.og_image,
            site_icon_url=site.site_icon_url,
            hero_image_url=site.hero_image_url,
            hero_poster_url=site.hero_poster_url,
            filing_info=site.filing_info,
            hero_actions=hero_actions,
            hero_video_url=site.hero_video_url,
            poem_source=site.poem_source,
            poem_hitokoto_types=list(site.poem_hitokoto_types or []),
            poem_hitokoto_keywords=list(site.poem_hitokoto_keywords or []),
            feature_flags=feature_flags,
        ),
        social_links=[SocialLinkRead.model_validate(link) for link in links],
        poems=[PoemRead.model_validate(poem) for poem in poems],
        navigation=navigation,
    )


def get_site_poem_preview(
    session: Session,
    *,
    mode: Literal["custom", "hitokoto"] | None = None,
    types: list[str] | None = None,
    strict: bool = False,
) -> SitePoemPreviewRead:
    site = repo.find_site_profile(session)
    if site is None:
        raise ResourceNotFound("site profile is missing")

    poems = repo.find_poems(session, site.id)
    requested_mode = mode or site.poem_source or "hitokoto"

    if requested_mode != "hitokoto":
        return SitePoemPreviewRead(mode="custom", content=_pick_custom_poem_content(poems))

    active_types = [
        item.strip() for item in (types if types is not None else list(site.poem_hitokoto_types or [])) if item.strip()
    ]

    try:
        return _get_cached_hitokoto_poem(active_types)
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        if strict:
            raise ValidationError("在线诗句获取失败，请稍后重试。") from exc
        return SitePoemPreviewRead(mode="custom", content=_pick_custom_poem_content(poems))


def get_page_copy(session: Session) -> PageCollectionRead:
    copies = repo.find_all_page_copies(session)

    items = []
    for page in copies:
        items.append(
            PageCopyRead(
                page_key=page.page_key,
                title=page.title,
                subtitle=page.subtitle,
                search_placeholder=page.search_placeholder,
                empty_message=page.empty_message,
                max_width=page.max_width,
                page_size=page.page_size,
                extras=page.extras,
            )
        )

    return PageCollectionRead(items=items)


def get_community_config(session: Session) -> CommunityConfigRead:
    config = repo.find_community_config(session)
    if config is None:
        raise ResourceNotFound("community config is missing")
    return CommunityConfigRead.model_validate(config)


def get_resume(session: Session) -> ResumeRead:
    basics = repo.find_resume_basics(session)
    if basics is None:
        raise ResourceNotFound("resume basics are missing")

    return ResumeRead(
        title=basics.title,
        summary=basics.summary,
        location=basics.location,
        email=basics.email,
        profile_image_url=basics.profile_image_url,
    )


load_site_bundle = get_site_config
load_pages_bundle = get_page_copy
load_community_bundle = get_community_config


def mcp_public_access_enabled(session: Session) -> bool:
    site = repo.find_site_profile(session)
    if site is None:
        return False
    flags = site.feature_flags or {}
    return bool(flags.get("mcp_public_access", False))


def _get_site_profile_orm(session: Session):
    """Return the primary SiteProfile ORM object, raising ResourceNotFound if missing."""
    from aerisun.domain.site_config.models import SiteProfile

    profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return profile


def get_site_profile_admin(session: Session) -> SiteProfileAdminRead:
    """Return the primary SiteProfile as a DTO."""
    profile = _get_site_profile_orm(session)
    return SiteProfileAdminRead.model_validate(profile)


def update_site_profile_admin(session: Session, payload: BaseModel) -> SiteProfileAdminRead:
    """Update the primary SiteProfile fields."""
    profile = _get_site_profile_orm(session)
    previous_title = profile.title
    previous_name = profile.name
    previous_hero_image_url = profile.hero_image_url
    previous_hero_poster_url = profile.hero_poster_url
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    session.commit()
    session.refresh(profile)
    if (
        profile.title != previous_title
        or profile.name != previous_name
        or profile.hero_image_url != previous_hero_image_url
        or profile.hero_poster_url != previous_hero_poster_url
    ):
        avatar_url = (profile.hero_image_url or "").strip() or (profile.hero_poster_url or "").strip()
        display_name = (profile.name or "").strip() or (profile.title or "").strip() or "管理员"
        if avatar_url:
            sync_admin_comment_profile(nick=display_name, avatar_url=avatar_url)
    return SiteProfileAdminRead.model_validate(profile)


def _get_community_config_orm(session: Session):
    """Return the CommunityConfig ORM object, raising ResourceNotFound if missing."""
    from aerisun.domain.site_config.models import CommunityConfig

    config = session.query(CommunityConfig).first()
    if config is None:
        raise ResourceNotFound("Community config not configured")
    return config


def get_community_config_admin(session: Session) -> CommunityConfigAdminRead:
    """Return CommunityConfig as a DTO."""
    config = _get_community_config_orm(session)
    return CommunityConfigAdminRead.model_validate(config)


def update_community_config_admin(session: Session, payload: BaseModel) -> CommunityConfigAdminRead:
    """Update CommunityConfig fields."""
    config = _get_community_config_orm(session)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    session.commit()
    session.refresh(config)
    return CommunityConfigAdminRead.model_validate(config)


def reorder_nav_items_admin(session: Session, reorder_list: list) -> list[NavItemAdminRead]:
    """Reorder nav items by updating parent_id and order_index."""
    from aerisun.domain.site_config.models import NavItem

    profile = _get_site_profile_orm(session)
    scoped = {
        item.id: item
        for item in session.query(NavItem)
        .filter(NavItem.site_profile_id == profile.id)
        .order_by(NavItem.order_index.asc())
        .all()
    }
    for reorder_item in reorder_list:
        nav_item = scoped.get(reorder_item.id)
        if nav_item is None:
            raise ResourceNotFound(f"NavItem {reorder_item.id} not found")
        nav_item.parent_id = reorder_item.parent_id
        nav_item.order_index = reorder_item.order_index
    session.commit()
    items = list(
        session.query(NavItem).filter(NavItem.site_profile_id == profile.id).order_by(NavItem.order_index.asc()).all()
    )
    return [NavItemAdminRead.model_validate(item) for item in items]


def site_profile_scoped_query(session: Session, model):
    """Return a query scoped to the primary SiteProfile."""
    profile = _get_site_profile_orm(session)
    return session.query(model).filter(model.site_profile_id == profile.id)


def attach_site_profile_id(session: Session, data: dict) -> dict:
    """Ensure data dict includes the primary site_profile_id."""
    profile = _get_site_profile_orm(session)
    if not data.get("site_profile_id"):
        data["site_profile_id"] = profile.id
    return data

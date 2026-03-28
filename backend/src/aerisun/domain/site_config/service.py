from __future__ import annotations

import json
import random
from collections import deque
from threading import Lock, Thread
from typing import Literal

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.site_config import repository as repo
from aerisun.domain.site_config.schemas import (
    CommunityConfigAdminRead,
    CommunityConfigRead,
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
HITOKOTO_CACHE_SIZE = 20
HITOKOTO_CACHE_REFILL_THRESHOLD = 10

HitokotoCacheKey = tuple[tuple[str, ...], tuple[str, ...]]

# Keep a small per-settings buffer so refreshes can render immediately.
_HITOKOTO_CACHE: dict[HitokotoCacheKey, deque[SitePoemPreviewRead]] = {}
_HITOKOTO_CACHE_REFRESHING: set[HitokotoCacheKey] = set()
_HITOKOTO_CACHE_LOCK = Lock()


def _normalize_poem_keywords(keywords: list[str]) -> list[str]:
    return [item.strip().lower() for item in keywords if item.strip()]


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


def _matches_hitokoto_keywords(payload: dict[str, object], keywords: list[str]) -> bool:
    if not keywords:
        return True

    haystack = " ".join(
        str(payload.get(field) or "").strip()
        for field in ("hitokoto", "from", "from_who")
        if str(payload.get(field) or "").strip()
    ).lower()
    return any(keyword in haystack for keyword in keywords)


def _pick_custom_poem_content(poems: list) -> str:
    candidates = [str(poem.content or "").strip() for poem in poems if str(poem.content or "").strip()]
    return random.choice(candidates) if candidates else ""


def _fetch_hitokoto_poem_with_client(
    client: httpx.Client,
    *,
    types: list[str],
    normalized_keywords: list[str],
) -> SitePoemPreviewRead:
    params = [("c", poem_type) for poem_type in types]
    last_payload: dict[str, object] | None = None

    for _ in range(HITOKOTO_RETRY_COUNT):
        response = client.get(HITOKOTO_ENDPOINT, params=params)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValidationError("在线诗句返回格式不正确。")

        last_payload = payload
        content = str(payload.get("hitokoto") or "").strip()
        if not content:
            continue
        if _matches_hitokoto_keywords(payload, normalized_keywords):
            return SitePoemPreviewRead(
                mode="hitokoto",
                content=content,
                attribution=_build_hitokoto_attribution(payload),
            )

    fallback_content = str((last_payload or {}).get("hitokoto") or "").strip()
    if not fallback_content:
        raise ValidationError("在线诗句暂时不可用，请稍后重试。")

    return SitePoemPreviewRead(
        mode="hitokoto",
        content=fallback_content,
        attribution=_build_hitokoto_attribution(last_payload or {}),
    )


def _build_hitokoto_cache_key(types: list[str], keywords: list[str]) -> HitokotoCacheKey:
    return tuple(types), tuple(_normalize_poem_keywords(keywords))


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
    keywords: list[str],
    target_size: int = HITOKOTO_CACHE_SIZE,
) -> int:
    with _HITOKOTO_CACHE_LOCK:
        current_size = len(_HITOKOTO_CACHE.get(cache_key, ()))

    missing = max(target_size - current_size, 0)
    if missing == 0:
        return 0

    normalized_keywords = _normalize_poem_keywords(keywords)
    new_items: list[SitePoemPreviewRead] = []
    last_error: Exception | None = None

    with httpx.Client(timeout=HITOKOTO_TIMEOUT, follow_redirects=True) as client:
        for _ in range(missing):
            try:
                new_items.append(
                    _fetch_hitokoto_poem_with_client(
                        client,
                        types=types,
                        normalized_keywords=normalized_keywords,
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
    keywords: list[str],
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
                keywords=keywords,
                target_size=HITOKOTO_CACHE_SIZE,
            )
        except (httpx.HTTPError, ValueError, ValidationError):
            pass
        finally:
            with _HITOKOTO_CACHE_LOCK:
                _HITOKOTO_CACHE_REFRESHING.discard(cache_key)

    Thread(target=_worker, daemon=True).start()


def _get_cached_hitokoto_poem(types: list[str], keywords: list[str]) -> SitePoemPreviewRead:
    normalized_types = _normalize_hitokoto_types(types)
    cache_key = _build_hitokoto_cache_key(normalized_types, keywords)

    poem, remaining = _pop_cached_hitokoto_poem(cache_key)
    if poem is None:
        _refill_hitokoto_cache(
            cache_key,
            types=normalized_types,
            keywords=keywords,
            target_size=HITOKOTO_CACHE_SIZE,
        )
        poem, remaining = _pop_cached_hitokoto_poem(cache_key)

    if poem is None:
        raise ValidationError("在线诗句获取失败，请稍后重试。")

    if remaining <= HITOKOTO_CACHE_REFILL_THRESHOLD:
        _schedule_hitokoto_cache_refill(
            cache_key,
            types=normalized_types,
            keywords=keywords,
        )

    return poem


def get_site_config(session: Session) -> SiteConfigRead:
    site = repo.find_site_profile(session)
    if site is None:
        raise ResourceNotFound("site profile is missing")

    links = repo.find_social_links(session, site.id)
    poems = repo.find_poems(session, site.id)

    hero_actions = json.loads(site.hero_actions) if site.hero_actions else []
    feature_flags = dict(site.feature_flags or {})

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
            footer_text=site.footer_text,
            author=site.author,
            og_image=site.og_image,
            site_icon_url=site.site_icon_url,
            hero_image_url=site.hero_image_url,
            hero_poster_url=site.hero_poster_url,
            meta_description=site.meta_description,
            copyright=site.copyright,
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
    keywords: list[str] | None = None,
    strict: bool = False,
) -> SitePoemPreviewRead:
    site = repo.find_site_profile(session)
    if site is None:
        raise ResourceNotFound("site profile is missing")

    poems = repo.find_poems(session, site.id)
    requested_mode = mode or site.poem_source or "custom"

    if requested_mode != "hitokoto":
        return SitePoemPreviewRead(mode="custom", content=_pick_custom_poem_content(poems))

    active_types = [
        item.strip() for item in (types if types is not None else list(site.poem_hitokoto_types or [])) if item.strip()
    ]
    active_keywords = [
        item.strip()
        for item in (keywords if keywords is not None else list(site.poem_hitokoto_keywords or []))
        if item.strip()
    ]

    try:
        return _get_cached_hitokoto_poem(active_types, active_keywords)
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        if strict:
            raise ValidationError("在线诗句获取失败，请稍后重试。") from exc
        return SitePoemPreviewRead(mode="custom", content=_pick_custom_poem_content(poems))


def get_page_copy(session: Session) -> PageCollectionRead:
    copies = repo.find_all_page_copies(session)
    options = repo.find_all_page_display_options(session)

    items = []
    for page in copies:
        option = options.get(page.page_key)
        items.append(
            PageCopyRead(
                page_key=page.page_key,
                label=page.label,
                nav_label=page.nav_label,
                title=page.title,
                subtitle=page.subtitle,
                description=page.description,
                search_placeholder=page.search_placeholder,
                empty_message=page.empty_message,
                max_width=page.max_width,
                page_size=page.page_size,
                download_label=page.download_label,
                enabled=True if option is None else option.is_enabled,
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
    previous_og_image = profile.og_image
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    session.commit()
    session.refresh(profile)
    if (
        profile.title != previous_title
        or profile.name != previous_name
        or profile.hero_image_url != previous_hero_image_url
        or profile.hero_poster_url != previous_hero_poster_url
        or profile.og_image != previous_og_image
    ):
        avatar_url = (
            (profile.hero_image_url or "").strip()
            or (profile.hero_poster_url or "").strip()
            or (profile.og_image or "").strip()
        )
        display_name = (
            (profile.name or "").strip() or (profile.title or "").strip() or (profile.author or "").strip() or "管理员"
        )
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


def get_resume_basics_admin(session: Session):
    """Return primary ResumeBasics, raising ResourceNotFound if missing."""
    from aerisun.domain.site_config.models import ResumeBasics

    basics = session.query(ResumeBasics).order_by(ResumeBasics.created_at.asc()).first()
    if basics is None:
        raise ResourceNotFound("Resume basics not configured")
    return basics


def resume_scoped_query(session: Session, model):
    """Return a query scoped to the primary ResumeBasics."""
    basics = get_resume_basics_admin(session)
    return session.query(model).filter(model.resume_basics_id == basics.id)


def attach_resume_basics_id(session: Session, data: dict) -> dict:
    """Ensure data dict includes the primary resume_basics_id."""
    basics = get_resume_basics_admin(session)
    if not data.get("resume_basics_id"):
        data["resume_basics_id"] = basics.id
    return data

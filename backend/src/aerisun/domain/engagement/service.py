from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import quote, urljoin

import httpx
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.engagement import repository as repo
from aerisun.domain.engagement.schemas import (
    CommentCollectionRead,
    CommentCreate,
    CommentCreateResponse,
    CommentRead,
    GuestbookCollectionRead,
    GuestbookCreate,
    GuestbookCreateResponse,
    GuestbookEntryRead,
    ReactionCreate,
    ReactionRead,
)
from aerisun.domain.exceptions import ResourceNotFound, StateConflict
from aerisun.domain.exceptions import ValidationError as DomainValidationError
from aerisun.domain.site_auth import repository as site_auth_repo
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.service import get_admin_comment_identity, is_site_user_admin
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.waline.service import (
    build_comment_path,
    create_waline_record,
    get_waline_nick_identity,
    get_waline_record_by_id,
    list_all_waline_records,
    list_records_for_url,
    normalize_comment_mail,
    normalize_comment_nick,
    update_waline_comment_avatars,
    upsert_waline_nick_identity,
)

DEFAULT_COMMENT_AVATAR_PRESETS = [
    {"key": "shiro", "label": "Shiro", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Shiro"},
    {"key": "glass", "label": "Glass", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Glass"},
    {"key": "aurora", "label": "Aurora", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Aurora"},
    {"key": "paper", "label": "Paper", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Paper"},
    {"key": "dawn", "label": "Dawn", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Dawn"},
    {"key": "pebble", "label": "Pebble", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Pebble"},
    {"key": "amber", "label": "Amber", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Amber"},
    {"key": "mint", "label": "Mint", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Mint"},
    {"key": "cinder", "label": "Cinder", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Cinder"},
    {"key": "tide", "label": "Tide", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Tide"},
    {"key": "plum", "label": "Plum", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Plum"},
    {"key": "linen", "label": "Linen", "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Linen"},
]
AVATAR_PICKER_COUNT = 16
AVATAR_POOL_SIZE = 1000
DICEBEAR_NOTIONISTS_BASE_URL = "https://api.dicebear.com/9.x/notionists/svg"


@dataclass(slots=True)
class AuthenticatedCommentProfile:
    nick: str
    mail: str
    link: str | None
    avatar_key: str
    avatar_url: str


def _avatar_for_name(name: str) -> str:
    return _avatar_url_for_seed(_avatar_seed(_normalize_avatar_identity(name), 0))


def _normalize_avatar_identity(value: str | None) -> str:
    normalized = " ".join((value or "").strip().split()).lower()
    return normalized or "visitor"


def _avatar_hash(value: str) -> int:
    hash_value = 0x811C9DC5
    for character in value:
        hash_value ^= ord(character)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return hash_value


def _seeded_random(seed_value: str) -> int:
    state = _avatar_hash(seed_value) or 1
    return state


def _next_seeded_random(state: int) -> tuple[int, float]:
    next_state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
    return next_state, next_state / 0x100000000


def _sample_avatar_indexes(identity: str, count: int = AVATAR_PICKER_COUNT) -> list[int]:
    normalized_identity = _normalize_avatar_identity(identity)
    pool = list(range(AVATAR_POOL_SIZE))
    state = _seeded_random(normalized_identity)

    for index in range(len(pool) - 1, 0, -1):
        state, random_value = _next_seeded_random(state)
        target = int(random_value * (index + 1))
        pool[index], pool[target] = pool[target], pool[index]

    return pool[:count]


def _avatar_seed(identity: str, index: int) -> str:
    return f"{_avatar_hash(f'{identity}:{index}'):08x}"


def _avatar_url_for_seed(seed: str) -> str:
    return f"{DICEBEAR_NOTIONISTS_BASE_URL}?seed={quote(seed)}"


def _build_avatar_candidates(identity: str, count: int = AVATAR_PICKER_COUNT) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for pool_index in _sample_avatar_indexes(identity, count):
        seed = _avatar_seed(_normalize_avatar_identity(identity), pool_index)
        candidates.append(
            {
                "key": seed,
                "label": f"Notionists {pool_index:03d}",
                "avatar_url": _avatar_url_for_seed(seed),
            }
        )
    return candidates


def _default_avatar_candidate(identity: str) -> tuple[str, str]:
    candidates = _build_avatar_candidates(identity)
    if not candidates:
        return _auto_avatar(identity)

    candidate = candidates[0]
    return candidate["key"], candidate["avatar_url"]


def _normalize_comment_avatar_key(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _site_user_id_from_avatar_key(avatar_key: str | None) -> str | None:
    normalized_avatar_key = _normalize_comment_avatar_key(avatar_key)
    if not normalized_avatar_key.startswith("site-user-"):
        return None
    site_user_id = normalized_avatar_key.removeprefix("site-user-").strip()
    return site_user_id or None


def _is_bound_admin_comment(
    session: Session,
    *,
    email: str | None,
    avatar_key: str | None,
) -> bool:
    site_user_id = _site_user_id_from_avatar_key(avatar_key)
    if site_user_id and site_auth_repo.find_admin_identity_for_user(session, site_user_id=site_user_id) is not None:
        return True

    normalized_email = _email_key(email)
    if not normalized_email:
        return False

    site_user = site_auth_repo.find_user_by_email(session, normalized_email)
    if site_user is not None and (
        site_auth_repo.find_admin_identity_for_user(session, site_user_id=site_user.id) is not None
    ):
        return True

    return site_auth_repo.find_admin_email_identity(session, email=normalized_email) is not None


def _build_authenticated_site_user_profile(
    session: Session,
    current_user: SiteUser,
    *,
    current_site_session: SiteUserSession | None = None,
) -> AuthenticatedCommentProfile:
    if is_site_user_admin(session, current_user, current_site_session):
        nick, avatar_key, avatar_url = get_admin_comment_identity(session)
        return AuthenticatedCommentProfile(
            nick=nick,
            mail=current_user.email,
            link=None,
            avatar_key=avatar_key,
            avatar_url=avatar_url,
        )

    return AuthenticatedCommentProfile(
        nick=current_user.display_name,
        mail=current_user.email,
        link=None,
        avatar_key=f"site-user-{current_user.id}",
        avatar_url=current_user.avatar_url,
    )


def _resolve_public_admin_profile(
    session: Session,
    *,
    fallback_name: str,
    fallback_avatar_url: str,
    is_author: bool,
) -> tuple[str, str]:
    if not is_author:
        return fallback_name, fallback_avatar_url

    nick, _avatar_key, avatar_url = get_admin_comment_identity(session)
    return nick, avatar_url or fallback_avatar_url


def _clean_display_name(name: str | None) -> str:
    cleaned = " ".join((name or "").strip().split())
    return cleaned or "访客"


def _name_key(name: str | None) -> str:
    return normalize_comment_nick(_clean_display_name(name))


def _email_key(email: str | None) -> str:
    return normalize_comment_mail(email)


def _resolve_waline_server_url(session: Session) -> str:
    config = site_config_repo.find_community_config(session)
    raw_server_url = (config.server_url if config and config.server_url else "").strip()
    if not raw_server_url:
        raw_server_url = get_settings().waline_server_url.strip()

    if raw_server_url.startswith(("http://", "https://")):
        return raw_server_url.rstrip("/")

    site_url = get_settings().site_url.strip().rstrip("/")
    return urljoin(f"{site_url}/", raw_server_url.lstrip("/")).rstrip("/")


def _load_authenticated_profile(session: Session, token: str) -> AuthenticatedCommentProfile:
    clean_token = token.strip()
    if not clean_token:
        raise DomainValidationError("登录状态已失效，请重新登录。")

    endpoint = f"{_resolve_waline_server_url(session)}/api/token"
    try:
        response = httpx.get(
            endpoint,
            headers={"Authorization": f"Bearer {clean_token}"},
            params={"lang": "zh-CN"},
            timeout=5.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DomainValidationError("登录状态校验失败，请重新登录。") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise DomainValidationError("登录状态校验失败，请重新登录。") from exc

    if not isinstance(payload, dict):
        raise DomainValidationError("登录状态校验失败，请重新登录。")

    if payload.get("errno") not in (None, 0):
        raise DomainValidationError(str(payload.get("errmsg") or "登录状态校验失败，请重新登录。"))

    raw_profile = payload.get("data")
    if not isinstance(raw_profile, dict) or not raw_profile.get("objectId"):
        raise DomainValidationError("登录状态已失效，请重新登录。")

    display_name = _clean_display_name(str(raw_profile.get("display_name") or raw_profile.get("nick") or "访客"))
    object_id = str(raw_profile.get("objectId") or "").strip()
    mail = _email_key(raw_profile.get("email"))
    if not mail:
        digest = sha256(clean_token.encode("utf-8")).hexdigest()[:12]
        mail = f"oauth-{object_id or digest}@waline.local"

    avatar_url = str(raw_profile.get("avatar") or "").strip() or _avatar_for_name(display_name)
    avatar_key = f"oauth-{object_id}" if object_id else f"oauth-{sha256(clean_token.encode('utf-8')).hexdigest()[:12]}"

    return AuthenticatedCommentProfile(
        nick=display_name,
        mail=mail,
        link=str(raw_profile.get("url") or "").strip() or None,
        avatar_key=avatar_key,
        avatar_url=avatar_url,
    )


def _load_avatar_presets() -> list[dict[str, str]]:
    presets: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for index, item in enumerate(DEFAULT_COMMENT_AVATAR_PRESETS):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or item.get("id") or f"preset-{index + 1}").strip()
        avatar_url = str(item.get("avatar_url") or item.get("src") or "").strip()
        if not key or not avatar_url or key in seen_keys:
            continue
        presets.append(
            {
                "key": key,
                "label": str(item.get("label") or item.get("name") or key).strip() or key,
                "avatar_url": avatar_url,
            }
        )
        seen_keys.add(key)

    return presets or [preset.copy() for preset in DEFAULT_COMMENT_AVATAR_PRESETS]


def _auto_avatar(seed: str) -> tuple[str, str]:
    digest = sha256(seed.encode("utf-8")).hexdigest()[:12]
    return (
        f"auto-{digest}",
        _avatar_url_for_seed(digest),
    )


def _stable_preset_order(presets: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    if not presets:
        return []
    start = int(sha256(seed.encode("utf-8")).hexdigest(), 16) % len(presets)
    return [presets[(start + index) % len(presets)] for index in range(len(presets))]


def _pick_available_avatar(
    presets: list[dict[str, str]],
    occupied_keys: set[str],
    seed: str,
) -> tuple[str, str]:
    for preset in _stable_preset_order(presets, seed):
        if preset["key"] not in occupied_keys:
            return preset["key"], preset["avatar_url"]
    return _auto_avatar(seed)


def _ensure_comment_avatar_assignments(session: Session, url: str) -> list:
    records = list_records_for_url(url=url, status=None, order="asc")
    if not records:
        return records

    assignments: dict[int, tuple[str, str]] = {}
    avatar_by_identity: dict[str, tuple[str, str]] = {}
    occupied_keys: set[str] = set()

    for record in records:
        identity_key = _email_key(record.mail) or _name_key(record.nick)
        if record.avatar_key and record.avatar_url:
            avatar_by_identity.setdefault(identity_key, (record.avatar_key, record.avatar_url))
            occupied_keys.add(record.avatar_key)
            continue

        if record.avatar_url and not record.avatar_key:
            synthetic_key = f"url-{sha256(record.avatar_url.encode('utf-8')).hexdigest()[:12]}"
            avatar_by_identity.setdefault(identity_key, (synthetic_key, record.avatar_url))
            occupied_keys.add(synthetic_key)
            assignments[record.id] = (synthetic_key, record.avatar_url)
            record.avatar_key = synthetic_key
            continue

        if record.avatar_key and record.avatar_url:
            avatar_by_identity.setdefault(identity_key, (record.avatar_key, record.avatar_url))
            occupied_keys.add(record.avatar_key)

    for record in records:
        if record.avatar_key and record.avatar_url:
            continue

        identity_key = _email_key(record.mail) or _name_key(record.nick)
        chosen = avatar_by_identity.get(identity_key)
        if chosen is None:
            chosen = _default_avatar_candidate(identity_key)
            if chosen[0] in occupied_keys:
                for candidate in _build_avatar_candidates(identity_key):
                    candidate_pair = (candidate["key"], candidate["avatar_url"])
                    if candidate_pair[0] not in occupied_keys:
                        chosen = candidate_pair
                        break
            avatar_by_identity[identity_key] = chosen
            occupied_keys.add(chosen[0])

        assignments[record.id] = chosen
        record.avatar_key, record.avatar_url = chosen

    if assignments:
        update_waline_comment_avatars(assignments=assignments)

    return records


def _validate_identity(name: str, email: str | None) -> tuple[str, str]:
    author_name = _clean_display_name(name)
    author_email = _email_key(email)
    if not author_email:
        raise DomainValidationError("请填写邮箱，昵称会和邮箱绑定。")

    existing = get_waline_nick_identity(nick=author_name)
    if existing is not None and _email_key(existing.mail) != author_email:
        raise StateConflict("这个昵称已经绑定了其他邮箱，请换一个昵称或使用原邮箱。")

    upsert_waline_nick_identity(nick=author_name, mail=author_email)
    return author_name, author_email


def _raise_login_required(surface: str) -> None:
    if surface == "guestbook":
        raise DomainValidationError("当前站点要求登录后才能留言。")

    raise DomainValidationError("当前站点要求登录后才能发表评论。")


def _email_login_enabled_for_comments(session: Session) -> bool:
    config = site_config_repo.find_community_config(session)
    if config is None:
        return True
    return bool(config.anonymous_enabled)


def _ensure_authenticated_comment_allowed(
    session: Session,
    *,
    surface: str,
    authenticated: bool = False,
    current_user: SiteUser | None = None,
) -> None:
    if not authenticated:
        _raise_login_required(surface)

    if current_user is None:
        return
    if is_site_user_admin(session, current_user):
        return
    if current_user.primary_auth_provider != "email":
        return
    if _email_login_enabled_for_comments(session):
        return

    if surface == "guestbook":
        raise DomainValidationError("当前站点未启用邮箱登录留言，请改用其他登录方式。")

    raise DomainValidationError("当前站点未启用邮箱登录评论，请改用其他登录方式。")


def ensure_comment_image_upload_allowed(session: Session) -> None:
    config = site_config_repo.find_community_config(session)
    if config is not None and not config.image_uploader:
        raise DomainValidationError("当前站点已关闭评论图片上传。")


def _resolve_avatar_selection(
    session: Session,
    *,
    url: str,
    author_name: str,
    author_email: str,
    requested_avatar_key: str | None,
) -> tuple[str, str]:
    records = _ensure_comment_avatar_assignments(session, url)
    author_identity_key = _email_key(author_email) or _name_key(author_name)

    for record in records:
        record_identity_key = _email_key(record.mail) or _name_key(record.nick)
        if record_identity_key == author_identity_key and record.avatar_key and record.avatar_url:
            return record.avatar_key, record.avatar_url

    presets = _load_avatar_presets()
    preset_by_key = {preset["key"]: preset for preset in presets}
    candidate_by_key = {candidate["key"]: candidate for candidate in _build_avatar_candidates(author_identity_key)}
    occupied_by_others = {
        record.avatar_key
        for record in records
        if record.avatar_key and (_email_key(record.mail) or _name_key(record.nick)) != author_identity_key
    }

    if requested_avatar_key:
        candidate = candidate_by_key.get(requested_avatar_key)
        if candidate is not None:
            return candidate["key"], candidate["avatar_url"]

        preset = preset_by_key.get(requested_avatar_key)
        if preset is None:
            raise DomainValidationError("所选头像不存在，请重新选择。")
        if requested_avatar_key in occupied_by_others:
            raise StateConflict("这个头像已经被当前页面里的其他昵称占用，请换一个。")
        return preset["key"], preset["avatar_url"]

    return _default_avatar_candidate(author_identity_key)


def _resolve_comment_sorting(session: Session) -> str:
    config = site_config_repo.find_community_config(session)
    sorting = (config.default_sorting if config else "").strip().lower()
    return sorting or "latest"


def _sort_guestbook_entries(
    items: list[GuestbookEntryRead],
    sorting: str,
) -> list[GuestbookEntryRead]:
    reverse = sorting != "oldest"
    return sorted(items, key=lambda item: item.created_at, reverse=reverse)


def _sort_comment_threads(
    items: list[CommentRead],
    sorting: str,
) -> list[CommentRead]:
    reverse = sorting != "oldest"
    return sorted(items, key=lambda item: item.created_at, reverse=reverse)


def _paginate_items(items: list, page: int, page_size: int) -> tuple[list, int, bool]:
    total = len(items)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return items[start:end], total, end < total


def _guestbook_entry_from_waline(session: Session, item) -> GuestbookEntryRead:
    is_author = _is_bound_admin_comment(
        session,
        email=item.mail,
        avatar_key=item.avatar_key,
    )
    fallback_name = item.nick or "访客"
    fallback_avatar_url = item.avatar_url or _avatar_for_name(fallback_name)
    display_name, display_avatar_url = _resolve_public_admin_profile(
        session,
        fallback_name=fallback_name,
        fallback_avatar_url=fallback_avatar_url,
        is_author=is_author,
    )
    return GuestbookEntryRead(
        id=str(item.id),
        name=display_name,
        website=item.link,
        body=item.comment,
        status=item.status,
        created_at=item.created_at,
        avatar=item.avatar_key or fallback_avatar_url,
        avatar_url=display_avatar_url,
        is_author=is_author,
    )


def list_public_guestbook_entries(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
) -> GuestbookCollectionRead:
    _ensure_comment_avatar_assignments(session, build_comment_path("guestbook", "guestbook"))
    sorting = _resolve_comment_sorting(session)
    items = list_all_waline_records(status="approved", guestbook_only=True)
    mapped = _sort_guestbook_entries(
        [_guestbook_entry_from_waline(session, item) for item in items],
        sorting,
    )
    paged_items, total, has_more = _paginate_items(mapped, page, page_size)
    return GuestbookCollectionRead(
        items=paged_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


def create_public_guestbook_entry(
    session: Session,
    payload: GuestbookCreate,
    *,
    current_user: SiteUser | None = None,
    current_site_session: SiteUserSession | None = None,
) -> GuestbookCreateResponse:
    if not payload.body.strip():
        raise DomainValidationError("留言内容不能为空。")

    auth_profile = None
    if current_user is not None:
        auth_profile = _build_authenticated_site_user_profile(
            session,
            current_user,
            current_site_session=current_site_session,
        )
    elif payload.auth_token:
        auth_profile = _load_authenticated_profile(session, payload.auth_token)
    _ensure_authenticated_comment_allowed(
        session,
        surface="guestbook",
        authenticated=auth_profile is not None,
        current_user=current_user,
    )

    if auth_profile is not None:
        author_name = auth_profile.nick
        author_email = auth_profile.mail
        website = payload.website.strip() if payload.website else auth_profile.link
        avatar_key = auth_profile.avatar_key
        avatar_url = auth_profile.avatar_url
    else:
        author_name, author_email = _validate_identity(payload.name, payload.email)
        website = payload.website.strip() if payload.website else None
        avatar_key, avatar_url = _resolve_avatar_selection(
            session,
            url=build_comment_path("guestbook", "guestbook"),
            author_name=author_name,
            author_email=author_email,
            requested_avatar_key=getattr(payload, "avatar_key", None),
        )

    from aerisun.domain.automation.events import emit_guestbook_pending

    entry = create_waline_record(
        comment=payload.body.strip(),
        nick=author_name,
        mail=author_email,
        link=website,
        status="pending",
        url=build_comment_path("guestbook", "guestbook"),
        avatar_key=avatar_key,
        avatar_url=avatar_url,
    )
    emit_guestbook_pending(
        session,
        entry_id=str(entry.id),
        author_name=entry.nick or "访客",
        body_preview=(entry.comment or "")[:240],
    )
    return GuestbookCreateResponse(
        item=GuestbookEntryRead(
            id=str(entry.id),
            name=entry.nick or "访客",
            website=entry.link,
            body=entry.comment,
            status=entry.status,
            created_at=entry.created_at,
            avatar=entry.avatar_key or entry.avatar_url,
            avatar_url=entry.avatar_url,
            is_author=_is_bound_admin_comment(
                session,
                email=entry.mail,
                avatar_key=entry.avatar_key,
            ),
        ),
        accepted=True,
    )


def _build_waline_comment_tree(session: Session, items) -> list[CommentRead]:
    by_parent: dict[int | None, list] = defaultdict(list)
    for item in items:
        by_parent[item.pid].append(item)

    def convert(node) -> CommentRead:
        raw_author_name = (node.nick or "访客").strip() or "访客"
        raw_avatar = node.avatar_url or _avatar_for_name(raw_author_name)
        is_author = _is_bound_admin_comment(
            session,
            email=node.mail,
            avatar_key=node.avatar_key,
        )
        author_name, avatar = _resolve_public_admin_profile(
            session,
            fallback_name=raw_author_name,
            fallback_avatar_url=raw_avatar,
            is_author=is_author,
        )
        return CommentRead(
            id=str(node.id),
            parent_id=str(node.pid) if node.pid is not None else None,
            author_name=author_name,
            body=node.comment,
            status=node.status,
            created_at=node.created_at,
            avatar=node.avatar_key or avatar,
            avatar_url=avatar,
            like_count=node.like,
            liked=False,
            is_author=is_author,
            replies=[convert(child) for child in by_parent.get(node.id, [])],
        )

    roots = by_parent.get(None, [])
    return [convert(root) for root in roots]


def list_public_comments(
    session: Session,
    content_type: str,
    content_slug: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> CommentCollectionRead:
    if not repo.content_exists(session, content_type, content_slug):
        raise ResourceNotFound(f"{content_type} content with slug '{content_slug}' was not found")

    url = build_comment_path(content_type, content_slug)
    _ensure_comment_avatar_assignments(session, url)
    items = list_records_for_url(
        url=url,
        status="approved",
        order="asc",
    )
    threads = _sort_comment_threads(_build_waline_comment_tree(session, items), _resolve_comment_sorting(session))
    paged_items, total, has_more = _paginate_items(threads, page, page_size)
    return CommentCollectionRead(
        items=paged_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


def create_public_comment(
    session: Session,
    content_type: str,
    content_slug: str,
    payload: CommentCreate,
    *,
    current_user: SiteUser | None = None,
    current_site_session: SiteUserSession | None = None,
) -> CommentCreateResponse:
    if not repo.content_exists(session, content_type, content_slug):
        raise ResourceNotFound(f"{content_type} content with slug '{content_slug}' was not found")
    if not payload.body.strip():
        raise DomainValidationError("评论内容不能为空。")

    auth_profile = None
    if current_user is not None:
        auth_profile = _build_authenticated_site_user_profile(
            session,
            current_user,
            current_site_session=current_site_session,
        )
    elif payload.auth_token:
        auth_profile = _load_authenticated_profile(session, payload.auth_token)
    _ensure_authenticated_comment_allowed(
        session,
        surface="comment",
        authenticated=auth_profile is not None,
        current_user=current_user,
    )

    if auth_profile is not None:
        author_name = auth_profile.nick
        author_email = auth_profile.mail
        avatar_key = auth_profile.avatar_key
        avatar_url = auth_profile.avatar_url
    else:
        author_name, author_email = _validate_identity(payload.author_name, payload.author_email)
        avatar_key, avatar_url = _resolve_avatar_selection(
            session,
            url=build_comment_path(content_type, content_slug),
            author_name=author_name,
            author_email=author_email,
            requested_avatar_key=getattr(payload, "avatar_key", None),
        )

    url = build_comment_path(content_type, content_slug)
    parent_id: int | None = None
    if payload.parent_id:
        try:
            parent_id = int(payload.parent_id)
        except ValueError as exc:
            raise ResourceNotFound(f"comment parent '{payload.parent_id}' was not found") from exc

        parent = get_waline_record_by_id(record_id=parent_id)
        if parent is None or parent.url != url:
            raise ResourceNotFound(f"comment parent '{payload.parent_id}' was not found")

    from aerisun.domain.automation.events import emit_comment_pending

    item = create_waline_record(
        comment=payload.body.strip(),
        nick=author_name,
        mail=author_email,
        link=None,
        status="pending",
        url=url,
        parent_id=parent_id,
        avatar_key=avatar_key,
        avatar_url=avatar_url,
    )
    emit_comment_pending(
        session,
        comment_id=str(item.id),
        content_type=content_type,
        content_slug=content_slug,
        author_name=item.nick or "访客",
        body_preview=(item.comment or "")[:240],
    )
    return CommentCreateResponse(
        item=CommentRead(
            id=str(item.id),
            parent_id=str(item.pid) if item.pid is not None else None,
            author_name=item.nick or "访客",
            body=item.comment,
            status=item.status,
            created_at=item.created_at,
            avatar=item.avatar_key or item.avatar_url,
            avatar_url=item.avatar_url or _avatar_for_name(item.nick or "访客"),
            like_count=item.like,
            liked=False,
            is_author=_is_bound_admin_comment(
                session,
                email=item.mail,
                avatar_key=item.avatar_key,
            ),
            replies=[],
        ),
        accepted=True,
    )


def register_public_reaction(session: Session, payload: ReactionCreate) -> ReactionRead:
    if not repo.content_exists(session, payload.content_type, payload.content_slug):
        raise ResourceNotFound(f"{payload.content_type} content with slug '{payload.content_slug}' was not found")

    if payload.client_token:
        existing = repo.find_reaction(
            session,
            content_type=payload.content_type,
            content_slug=payload.content_slug,
            reaction_type=payload.reaction_type,
            client_token=payload.client_token,
        )
        if existing is None:
            repo.create_reaction(
                session,
                content_type=payload.content_type,
                content_slug=payload.content_slug,
                reaction_type=payload.reaction_type,
                client_token=payload.client_token,
            )
            session.commit()
    else:
        repo.create_reaction(
            session,
            content_type=payload.content_type,
            content_slug=payload.content_slug,
            reaction_type=payload.reaction_type,
            client_token=None,
        )
        session.commit()

    total = repo.count_reactions(
        session,
        content_type=payload.content_type,
        content_slug=payload.content_slug,
        reaction_type=payload.reaction_type,
    )

    return ReactionRead(
        content_type=payload.content_type,
        content_slug=payload.content_slug,
        reaction_type=payload.reaction_type,
        total=total,
    )


def read_public_reaction(
    session: Session,
    content_type: str,
    content_slug: str,
    reaction_type: str,
) -> ReactionRead:
    if not repo.content_exists(session, content_type, content_slug):
        raise ResourceNotFound(f"{content_type} content with slug '{content_slug}' was not found")

    total = repo.count_reactions(
        session,
        content_type=content_type,
        content_slug=content_slug,
        reaction_type=reaction_type,
    )

    return ReactionRead(
        content_type=content_type,
        content_slug=content_slug,
        reaction_type=reaction_type,
        total=total,
    )


# ---------------------------------------------------------------------------
# Admin moderation functions
# ---------------------------------------------------------------------------


def _normalize_moderation_auth_provider(provider: str | None) -> str | None:
    candidate = " ".join((provider or "").strip().lower().split())
    if candidate in {"email", "google", "github"}:
        return candidate
    return None


def _resolve_moderation_auth_provider(
    session: Session,
    *,
    email: str | None,
    avatar_key: str | None,
) -> str | None:
    from aerisun.domain.site_auth.shared import ALLOWED_OAUTH_PROVIDERS

    normalized_email = normalize_comment_mail(email)
    normalized_avatar_key = _normalize_comment_avatar_key(avatar_key)

    site_user_id = _site_user_id_from_avatar_key(normalized_avatar_key)
    if site_user_id:
        site_user = site_auth_repo.find_user_by_id(session, site_user_id)
        provider = _normalize_moderation_auth_provider(
            site_user.primary_auth_provider if site_user else None,
        )
        if provider:
            return provider

    if normalized_email:
        site_user = site_auth_repo.find_user_by_email(session, normalized_email)
        provider = _normalize_moderation_auth_provider(
            site_user.primary_auth_provider if site_user else None,
        )
        if provider:
            return provider

    if normalized_email:
        admin_identity = site_auth_repo.find_admin_email_identity(session, email=normalized_email)
        provider = _normalize_moderation_auth_provider(
            admin_identity.provider if admin_identity else None,
        )
        if provider:
            return provider

        for provider_name in ALLOWED_OAUTH_PROVIDERS:
            account = site_auth_repo.find_oauth_account_by_email(
                session,
                provider=provider_name,
                email=normalized_email,
            )
            if account is not None:
                return provider_name

        if normalized_email.endswith("@waline.local") and normalized_avatar_key.startswith("oauth-"):
            return None
        return "email"

    return None


def _comment_admin_read_from_waline(session: Session, record):
    """Map a Waline record to CommentAdminRead schema."""
    from aerisun.domain.ops.schemas import CommentAdminRead
    from aerisun.domain.waline.service import parse_comment_path

    content_type, content_slug = parse_comment_path(record.url)
    return CommentAdminRead(
        id=str(record.id),
        content_type=content_type,
        content_slug=content_slug,
        parent_id=str(record.pid) if record.pid is not None else None,
        author_name=record.nick or "访客",
        author_email=record.mail,
        auth_provider=_resolve_moderation_auth_provider(
            session,
            email=record.mail,
            avatar_key=record.avatar_key,
        ),
        body=record.comment,
        status=record.status,
        created_at=record.inserted_at,
        updated_at=record.updated_at,
    )


def _guestbook_admin_read_from_waline(session: Session, record):
    """Map a Waline record to GuestbookAdminRead schema."""
    from aerisun.domain.ops.schemas import GuestbookAdminRead

    return GuestbookAdminRead(
        id=str(record.id),
        name=record.nick or "访客",
        email=record.mail,
        auth_provider=_resolve_moderation_auth_provider(
            session,
            email=record.mail,
            avatar_key=record.avatar_key,
        ),
        website=record.link,
        body=record.comment,
        status=record.status,
        created_at=record.inserted_at,
        updated_at=record.updated_at,
    )


def list_admin_comments(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    path: str | None = None,
    surface: str | None = None,
    keyword: str | None = None,
    author: str | None = None,
    email: str | None = None,
    sort: str | None = None,
) -> dict:
    from aerisun.domain.waline.service import list_waline_records

    items, total = list_waline_records(
        page=page,
        page_size=page_size,
        status=status,
        path=path,
        surface=surface,
        keyword=keyword,
        author=author,
        email=email,
        sort=sort,
    )
    return {
        "items": [_comment_admin_read_from_waline(session, item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_admin_guestbook(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    path: str | None = None,
    keyword: str | None = None,
    author: str | None = None,
    email: str | None = None,
    sort: str | None = None,
) -> dict:
    from aerisun.domain.waline.service import list_guestbook_records as _list_gb

    items, total = _list_gb(
        page=page,
        page_size=page_size,
        status=status,
        path=path,
        keyword=keyword,
        author=author,
        email=email,
        sort=sort,
    )
    return {
        "items": [_guestbook_admin_read_from_waline(session, item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def moderate_comment(session: Session, comment_id: int, action: str, reason: str | None = None):
    """Moderate a comment. Returns CommentAdminRead or None for delete. Raises LookupError/ValueError."""
    from aerisun.domain.automation.events import emit_comment_moderated
    from aerisun.domain.ops.models import ModerationRecord
    from aerisun.domain.waline.service import moderate_waline_record

    if action not in {"approve", "reject", "delete"}:
        raise DomainValidationError("Invalid action")

    result = moderate_waline_record(record_id=comment_id, action=action)

    if result is None:
        raise ResourceNotFound("Comment not found")

    record = ModerationRecord(
        target_type="comment",
        target_id=str(comment_id),
        action=action,
        reason=reason,
    )
    session.add(record)
    session.commit()
    emit_comment_moderated(session, comment_id=str(comment_id), action=action, reason=reason)

    if action == "delete":
        return None
    return _comment_admin_read_from_waline(session, result)


def moderate_guestbook_entry(session: Session, entry_id: int, action: str, reason: str | None = None):
    """Moderate a guestbook entry. Returns GuestbookAdminRead or None for delete. Raises LookupError/ValueError."""
    from aerisun.domain.automation.events import emit_guestbook_moderated
    from aerisun.domain.ops.models import ModerationRecord
    from aerisun.domain.waline.service import moderate_waline_record

    if action not in {"approve", "reject", "delete"}:
        raise DomainValidationError("Invalid action")

    result = moderate_waline_record(record_id=entry_id, action=action)

    if result is None:
        raise ResourceNotFound("Guestbook entry not found")

    record = ModerationRecord(
        target_type="guestbook",
        target_id=str(entry_id),
        action=action,
        reason=reason,
    )
    session.add(record)
    session.commit()
    emit_guestbook_moderated(session, entry_id=str(entry_id), action=action, reason=reason)

    if action == "delete":
        return None
    return _guestbook_admin_read_from_waline(session, result)

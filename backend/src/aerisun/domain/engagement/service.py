from __future__ import annotations

from collections import defaultdict
from hashlib import sha256

from sqlalchemy.orm import Session

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
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.waline.service import (
    build_comment_path,
    create_waline_record,
    get_waline_nick_identity,
    get_waline_record_by_id,
    list_guestbook_records,
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


def _avatar_for_name(name: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={name}"


def _is_author_name(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized in {"博主", "felix", "aerisun"}


def _clean_display_name(name: str | None) -> str:
    cleaned = " ".join((name or "").strip().split())
    return cleaned or "访客"


def _name_key(name: str | None) -> str:
    return normalize_comment_nick(_clean_display_name(name))


def _email_key(email: str | None) -> str:
    return normalize_comment_mail(email)


def _load_avatar_presets(session: Session) -> list[dict[str, str]]:
    config = site_config_repo.find_community_config(session)
    raw_presets = config.avatar_presets if config and config.avatar_presets else DEFAULT_COMMENT_AVATAR_PRESETS

    presets: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for index, item in enumerate(raw_presets):
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
        f"https://api.dicebear.com/9.x/notionists/svg?seed={digest}",
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
    presets = _load_avatar_presets(session)
    valid_preset_keys = {preset["key"] for preset in presets}
    records = list_records_for_url(url=url, status=None, order="asc")
    if not records:
        return records

    assignments: dict[int, tuple[str, str]] = {}
    avatar_by_name: dict[str, tuple[str, str]] = {}
    occupied_keys: set[str] = set()

    for record in records:
        name_key = _name_key(record.nick)
        if record.avatar_key and record.avatar_url:
            avatar_by_name.setdefault(name_key, (record.avatar_key, record.avatar_url))
            occupied_keys.add(record.avatar_key)
            continue

        if record.avatar_url and not record.avatar_key:
            synthetic_key = f"url-{sha256(record.avatar_url.encode('utf-8')).hexdigest()[:12]}"
            avatar_by_name.setdefault(name_key, (synthetic_key, record.avatar_url))
            occupied_keys.add(synthetic_key)
            assignments[record.id] = (synthetic_key, record.avatar_url)
            record.avatar_key = synthetic_key
            continue

        if record.avatar_key and record.avatar_key not in valid_preset_keys and record.avatar_url:
            avatar_by_name.setdefault(name_key, (record.avatar_key, record.avatar_url))
            occupied_keys.add(record.avatar_key)

    for record in records:
        if record.avatar_key and record.avatar_url:
            continue

        name_key = _name_key(record.nick)
        chosen = avatar_by_name.get(name_key)
        if chosen is None:
            chosen = _pick_available_avatar(
                presets,
                occupied_keys,
                f"{url}:{name_key}:{_email_key(record.mail)}",
            )
            avatar_by_name[name_key] = chosen
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


def _resolve_avatar_selection(
    session: Session,
    *,
    url: str,
    author_name: str,
    author_email: str,
    requested_avatar_key: str | None,
) -> tuple[str, str]:
    records = _ensure_comment_avatar_assignments(session, url)
    author_name_key = _name_key(author_name)

    for record in records:
        if _name_key(record.nick) == author_name_key and record.avatar_key and record.avatar_url:
            return record.avatar_key, record.avatar_url

    presets = _load_avatar_presets(session)
    preset_by_key = {preset["key"]: preset for preset in presets}
    occupied_by_others = {
        record.avatar_key for record in records if record.avatar_key and _name_key(record.nick) != author_name_key
    }

    if requested_avatar_key:
        preset = preset_by_key.get(requested_avatar_key)
        if preset is None:
            raise DomainValidationError("所选头像不存在，请重新选择。")
        if requested_avatar_key in occupied_by_others:
            raise StateConflict("这个头像已经被当前页面里的其他昵称占用，请换一个。")
        return preset["key"], preset["avatar_url"]

    return _pick_available_avatar(
        presets,
        occupied_by_others,
        f"{url}:{author_name_key}:{author_email}",
    )


def list_public_guestbook_entries(session: Session, limit: int = 50) -> GuestbookCollectionRead:
    _ensure_comment_avatar_assignments(session, build_comment_path("guestbook", "guestbook"))
    items, _total = list_guestbook_records(page=1, page_size=limit, status="approved")
    return GuestbookCollectionRead(
        items=[
            GuestbookEntryRead(
                id=str(item.id),
                name=item.nick or "访客",
                website=item.link,
                body=item.comment,
                status=item.status,
                created_at=item.created_at,
                avatar=item.avatar_key or item.avatar_url or _avatar_for_name(item.nick or "访客"),
                avatar_url=item.avatar_url or _avatar_for_name(item.nick or "访客"),
            )
            for item in items
        ]
    )


def create_public_guestbook_entry(session: Session, payload: GuestbookCreate) -> GuestbookCreateResponse:
    if not payload.body.strip():
        raise DomainValidationError("留言内容不能为空。")
    author_name, author_email = _validate_identity(payload.name, payload.email)
    avatar_key, avatar_url = _resolve_avatar_selection(
        session,
        url=build_comment_path("guestbook", "guestbook"),
        author_name=author_name,
        author_email=author_email,
        requested_avatar_key=getattr(payload, "avatar_key", None),
    )
    entry = create_waline_record(
        comment=payload.body.strip(),
        nick=author_name,
        mail=author_email,
        link=payload.website.strip() if payload.website else None,
        status="pending",
        url=build_comment_path("guestbook", "guestbook"),
        avatar_key=avatar_key,
        avatar_url=avatar_url,
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
        ),
        accepted=True,
    )


def _build_waline_comment_tree(items) -> list[CommentRead]:
    by_parent: dict[int | None, list] = defaultdict(list)
    for item in items:
        by_parent[item.pid].append(item)

    def convert(node) -> CommentRead:
        author_name = (node.nick or "访客").strip() or "访客"
        avatar = node.avatar_url or _avatar_for_name(author_name)
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
            is_author=_is_author_name(author_name),
            replies=[convert(child) for child in by_parent.get(node.id, [])],
        )

    roots = by_parent.get(None, [])
    return [convert(root) for root in roots]


def list_public_comments(session: Session, content_type: str, content_slug: str) -> CommentCollectionRead:
    if not repo.content_exists(session, content_type, content_slug):
        raise ResourceNotFound(f"{content_type} content with slug '{content_slug}' was not found")

    url = build_comment_path(content_type, content_slug)
    _ensure_comment_avatar_assignments(session, url)
    items = list_records_for_url(
        url=url,
        status="approved",
        order="asc",
    )
    return CommentCollectionRead(items=_build_waline_comment_tree(items))


def create_public_comment(
    session: Session,
    content_type: str,
    content_slug: str,
    payload: CommentCreate,
) -> CommentCreateResponse:
    if not repo.content_exists(session, content_type, content_slug):
        raise ResourceNotFound(f"{content_type} content with slug '{content_slug}' was not found")
    if not payload.body.strip():
        raise DomainValidationError("评论内容不能为空。")

    author_name, author_email = _validate_identity(payload.author_name, payload.author_email)
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

    avatar_key, avatar_url = _resolve_avatar_selection(
        session,
        url=url,
        author_name=author_name,
        author_email=author_email,
        requested_avatar_key=getattr(payload, "avatar_key", None),
    )
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
            is_author=_is_author_name(item.nick or "访客"),
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


def _comment_admin_read_from_waline(record):
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
        body=record.comment,
        status=record.status,
        created_at=record.inserted_at,
        updated_at=record.updated_at,
    )


def _guestbook_admin_read_from_waline(record):
    """Map a Waline record to GuestbookAdminRead schema."""
    from aerisun.domain.ops.schemas import GuestbookAdminRead

    return GuestbookAdminRead(
        id=str(record.id),
        name=record.nick or "访客",
        email=record.mail,
        website=record.link,
        body=record.comment,
        status=record.status,
        created_at=record.inserted_at,
        updated_at=record.updated_at,
    )


def list_admin_comments(
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
        "items": [_comment_admin_read_from_waline(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_admin_guestbook(
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
        "items": [_guestbook_admin_read_from_waline(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def moderate_comment(session: Session, comment_id: int, action: str, reason: str | None = None):
    """Moderate a comment. Returns CommentAdminRead or None for delete. Raises LookupError/ValueError."""
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

    if action == "delete":
        return None
    return _comment_admin_read_from_waline(result)


def moderate_guestbook_entry(session: Session, entry_id: int, action: str, reason: str | None = None):
    """Moderate a guestbook entry. Returns GuestbookAdminRead or None for delete. Raises LookupError/ValueError."""
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

    if action == "delete":
        return None
    return _guestbook_admin_read_from_waline(result)

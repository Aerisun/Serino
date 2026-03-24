from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Reaction
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
from aerisun.domain.waline.service import (
    build_comment_path,
    create_waline_record,
    get_waline_record_by_id,
    list_guestbook_records,
    list_records_for_url,
)

CONTENT_MODELS = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


def _avatar_for_name(name: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={name}"


def _is_author_name(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized in {"博主", "felix", "aerisun"}


def _content_exists(session: Session, content_type: str, content_slug: str) -> bool:
    model = CONTENT_MODELS.get(content_type)
    if model is None:
        return False
    return (
        session.scalar(
            select(func.count(model.id)).where(
                model.slug == content_slug,
                model.status == "published",
                model.visibility == "public",
            )
        )
        or 0
    ) > 0


def list_public_guestbook_entries(session: Session, limit: int = 50) -> GuestbookCollectionRead:
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
                avatar=_avatar_for_name(item.nick or "访客"),
                avatar_url=_avatar_for_name(item.nick or "访客"),
            )
            for item in items
        ]
    )


def create_public_guestbook_entry(session: Session, payload: GuestbookCreate) -> GuestbookCreateResponse:
    entry = create_waline_record(
        comment=payload.body.strip(),
        nick=payload.name.strip(),
        mail=payload.email.strip() if payload.email else None,
        link=payload.website.strip() if payload.website else None,
        status="pending",
        url=build_comment_path("guestbook", "guestbook"),
    )
    avatar = _avatar_for_name(entry.nick or "访客")
    return GuestbookCreateResponse(
        item=GuestbookEntryRead(
            id=str(entry.id),
            name=entry.nick or "访客",
            website=entry.link,
            body=entry.comment,
            status=entry.status,
            created_at=entry.created_at,
            avatar=avatar,
            avatar_url=avatar,
        ),
        accepted=True,
    )


def _build_waline_comment_tree(items) -> list[CommentRead]:
    by_parent: dict[int | None, list] = defaultdict(list)
    for item in items:
        by_parent[item.pid].append(item)

    def convert(node) -> CommentRead:
        author_name = (node.nick or "访客").strip() or "访客"
        avatar = _avatar_for_name(author_name)
        return CommentRead(
            id=str(node.id),
            parent_id=str(node.pid) if node.pid is not None else None,
            author_name=author_name,
            body=node.comment,
            status=node.status,
            created_at=node.created_at,
            avatar=avatar,
            avatar_url=avatar,
            like_count=node.like,
            liked=False,
            is_author=_is_author_name(author_name),
            replies=[convert(child) for child in by_parent.get(node.id, [])],
        )

    roots = by_parent.get(None, [])
    return [convert(root) for root in roots]


def list_public_comments(session: Session, content_type: str, content_slug: str) -> CommentCollectionRead:
    if not _content_exists(session, content_type, content_slug):
        raise LookupError(f"{content_type} content with slug '{content_slug}' was not found")

    items = list_records_for_url(
        url=build_comment_path(content_type, content_slug),
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
    if not _content_exists(session, content_type, content_slug):
        raise LookupError(f"{content_type} content with slug '{content_slug}' was not found")

    parent_id: int | None = None
    if payload.parent_id:
        try:
            parent_id = int(payload.parent_id)
        except ValueError as exc:
            raise LookupError(f"comment parent '{payload.parent_id}' was not found") from exc

        parent = get_waline_record_by_id(record_id=parent_id)
        if parent is None or parent.url != build_comment_path(content_type, content_slug):
            raise LookupError(f"comment parent '{payload.parent_id}' was not found")

    item = create_waline_record(
        comment=payload.body.strip(),
        nick=payload.author_name.strip(),
        mail=payload.author_email.strip() if payload.author_email else None,
        link=None,
        status="pending",
        url=build_comment_path(content_type, content_slug),
        parent_id=parent_id,
    )
    return CommentCreateResponse(
        item=CommentRead(
            id=str(item.id),
            parent_id=str(item.pid) if item.pid is not None else None,
            author_name=item.nick or "访客",
            body=item.comment,
            status=item.status,
            created_at=item.created_at,
            avatar=_avatar_for_name(item.nick or "访客"),
            avatar_url=_avatar_for_name(item.nick or "访客"),
            like_count=item.like,
            liked=False,
            is_author=_is_author_name(item.nick or "访客"),
            replies=[],
        ),
        accepted=True,
    )


def register_public_reaction(session: Session, payload: ReactionCreate) -> ReactionRead:
    if not _content_exists(session, payload.content_type, payload.content_slug):
        raise LookupError(f"{payload.content_type} content with slug '{payload.content_slug}' was not found")

    if payload.client_token:
        existing = session.scalars(
            select(Reaction).where(
                Reaction.content_type == payload.content_type,
                Reaction.content_slug == payload.content_slug,
                Reaction.reaction_type == payload.reaction_type,
                Reaction.client_token == payload.client_token,
            )
        ).first()
        if existing is None:
            session.add(
                Reaction(
                    content_type=payload.content_type,
                    content_slug=payload.content_slug,
                    reaction_type=payload.reaction_type,
                    client_token=payload.client_token,
                )
            )
            session.commit()
    else:
        session.add(
            Reaction(
                content_type=payload.content_type,
                content_slug=payload.content_slug,
                reaction_type=payload.reaction_type,
                client_token=None,
            )
        )
        session.commit()

    total = (
        session.scalar(
            select(func.count(Reaction.id)).where(
                Reaction.content_type == payload.content_type,
                Reaction.content_slug == payload.content_slug,
                Reaction.reaction_type == payload.reaction_type,
            )
        )
        or 0
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
    if not _content_exists(session, content_type, content_slug):
        raise LookupError(f"{content_type} content with slug '{content_slug}' was not found")

    total = (
        session.scalar(
            select(func.count(Reaction.id)).where(
                Reaction.content_type == content_type,
                Reaction.content_slug == content_slug,
                Reaction.reaction_type == reaction_type,
            )
        )
        or 0
    )

    return ReactionRead(
        content_type=content_type,
        content_slug=content_slug,
        reaction_type=reaction_type,
        total=total,
    )

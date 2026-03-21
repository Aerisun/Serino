from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.models import Comment, DiaryEntry, ExcerptEntry, GuestbookEntry, PostEntry, Reaction, ThoughtEntry
from aerisun.schemas import (
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
    items = session.scalars(
        select(GuestbookEntry)
        .where(GuestbookEntry.status == "approved")
        .order_by(GuestbookEntry.created_at.desc())
        .limit(limit)
    ).all()
    return GuestbookCollectionRead(
        items=[
            GuestbookEntryRead(
                id=item.id,
                name=item.name,
                website=item.website,
                body=item.body,
                status=item.status,
                created_at=item.created_at,
                avatar=_avatar_for_name(item.name),
                avatar_url=_avatar_for_name(item.name),
            )
            for item in items
        ]
    )


def create_public_guestbook_entry(session: Session, payload: GuestbookCreate) -> GuestbookCreateResponse:
    entry = GuestbookEntry(
        name=payload.name.strip(),
        email=payload.email.strip() if payload.email else None,
        website=payload.website.strip() if payload.website else None,
        body=payload.body.strip(),
        status="pending",
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    avatar = _avatar_for_name(entry.name)
    return GuestbookCreateResponse(
        item=GuestbookEntryRead(
            id=entry.id,
            name=entry.name,
            website=entry.website,
            body=entry.body,
            status=entry.status,
            created_at=entry.created_at,
            avatar=avatar,
            avatar_url=avatar,
        ),
        accepted=True,
    )


def _build_comment_tree(items: list[Comment]) -> list[CommentRead]:
    by_parent: dict[str | None, list[Comment]] = defaultdict(list)
    for item in items:
        by_parent[item.parent_id].append(item)

    def convert(node: Comment) -> CommentRead:
        avatar = _avatar_for_name(node.author_name)
        return CommentRead(
            id=node.id,
            parent_id=node.parent_id,
            author_name=node.author_name,
            body=node.body,
            status=node.status,
            created_at=node.created_at,
            avatar=avatar,
            avatar_url=avatar,
            like_count=0,
            liked=False,
            is_author=_is_author_name(node.author_name),
            replies=[convert(child) for child in by_parent.get(node.id, [])],
        )

    roots = by_parent.get(None, [])
    return [convert(root) for root in roots]


def list_public_comments(session: Session, content_type: str, content_slug: str) -> CommentCollectionRead:
    if not _content_exists(session, content_type, content_slug):
        raise LookupError(f"{content_type} content with slug '{content_slug}' was not found")

    items = session.scalars(
        select(Comment)
        .where(
            Comment.content_type == content_type,
            Comment.content_slug == content_slug,
            Comment.status == "approved",
        )
        .order_by(Comment.created_at.asc())
    ).all()
    return CommentCollectionRead(items=_build_comment_tree(items))


def create_public_comment(
    session: Session,
    content_type: str,
    content_slug: str,
    payload: CommentCreate,
) -> CommentCreateResponse:
    if not _content_exists(session, content_type, content_slug):
        raise LookupError(f"{content_type} content with slug '{content_slug}' was not found")

    if payload.parent_id:
        parent_exists = (
            session.scalar(
                select(func.count(Comment.id)).where(
                    Comment.id == payload.parent_id,
                    Comment.content_type == content_type,
                    Comment.content_slug == content_slug,
                )
            )
            or 0
        ) > 0
        if not parent_exists:
            raise LookupError(f"comment parent '{payload.parent_id}' was not found")

    item = Comment(
        content_type=content_type,
        content_slug=content_slug,
        parent_id=payload.parent_id,
        author_name=payload.author_name.strip(),
        author_email=payload.author_email.strip() if payload.author_email else None,
        body=payload.body.strip(),
        status="pending",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return CommentCreateResponse(
        item=CommentRead(
            id=item.id,
            parent_id=item.parent_id,
            author_name=item.author_name,
            body=item.body,
            status=item.status,
            created_at=item.created_at,
            avatar=_avatar_for_name(item.author_name),
            avatar_url=_avatar_for_name(item.author_name),
            like_count=0,
            liked=False,
            is_author=_is_author_name(item.author_name),
            replies=[],
        ),
        accepted=True,
    )


def register_public_reaction(session: Session, payload: ReactionCreate) -> ReactionRead:
    if not _content_exists(session, payload.content_type, payload.content_slug):
        raise LookupError(
            f"{payload.content_type} content with slug '{payload.content_slug}' was not found"
        )

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

    total = session.scalar(
        select(func.count(Reaction.id)).where(
            Reaction.content_type == payload.content_type,
            Reaction.content_slug == payload.content_slug,
            Reaction.reaction_type == payload.reaction_type,
        )
    ) or 0

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

    total = session.scalar(
        select(func.count(Reaction.id)).where(
            Reaction.content_type == content_type,
            Reaction.content_slug == content_slug,
            Reaction.reaction_type == reaction_type,
        )
    ) or 0

    return ReactionRead(
        content_type=content_type,
        content_slug=content_slug,
        reaction_type=reaction_type,
        total=total,
    )

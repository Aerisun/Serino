from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Reaction

CONTENT_MODELS: dict[str, type] = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


def content_exists(session: Session, content_type: str, content_slug: str) -> bool:
    """Check if a published public content item exists."""
    if content_type == "friends":
        return content_slug == "friends"

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


def find_reaction(
    session: Session,
    content_type: str,
    content_slug: str,
    reaction_type: str,
    client_token: str,
) -> Reaction | None:
    """Find an existing reaction by content+type+token."""
    return session.scalars(
        select(Reaction).where(
            Reaction.content_type == content_type,
            Reaction.content_slug == content_slug,
            Reaction.reaction_type == reaction_type,
            Reaction.client_token == client_token,
        )
    ).first()


def create_reaction(session: Session, **kwargs) -> Reaction:
    """Create a new Reaction record. Caller must commit."""
    reaction = Reaction(**kwargs)
    session.add(reaction)
    return reaction


def count_reactions(
    session: Session,
    content_type: str,
    content_slug: str,
    reaction_type: str,
) -> int:
    """Count total reactions for a given content+type."""
    return (
        session.scalar(
            select(func.count(Reaction.id)).where(
                Reaction.content_type == content_type,
                Reaction.content_slug == content_slug,
                Reaction.reaction_type == reaction_type,
            )
        )
        or 0
    )

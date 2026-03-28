from __future__ import annotations

from uuid import uuid4

from aerisun.domain.automation.models import AutomationEvent
from aerisun.domain.automation.service import emit_event


def emit_comment_pending(
    session,
    *,
    comment_id: str,
    content_type: str,
    content_slug: str,
    author_name: str,
    body_preview: str,
) -> None:
    event = AutomationEvent(
        event_type="comment.pending",
        event_id=uuid4().hex,
        target_type="comment",
        target_id=comment_id,
        payload={
            "comment_id": comment_id,
            "content_type": content_type,
            "content_slug": content_slug,
            "author_name": author_name,
            "body_preview": body_preview,
        },
    )
    emit_event(session, event)


def emit_guestbook_pending(
    session,
    *,
    entry_id: str,
    author_name: str,
    body_preview: str,
) -> None:
    event = AutomationEvent(
        event_type="guestbook.pending",
        event_id=uuid4().hex,
        target_type="guestbook",
        target_id=entry_id,
        payload={
            "entry_id": entry_id,
            "author_name": author_name,
            "body_preview": body_preview,
        },
    )
    emit_event(session, event)


def emit_comment_moderated(session, *, comment_id: str, action: str, reason: str | None = None) -> None:
    event = AutomationEvent(
        event_type=f"comment.{action}",
        event_id=uuid4().hex,
        target_type="comment",
        target_id=comment_id,
        payload={"comment_id": comment_id, "action": action, "reason": reason},
    )
    emit_event(session, event)


def emit_guestbook_moderated(session, *, entry_id: str, action: str, reason: str | None = None) -> None:
    event = AutomationEvent(
        event_type=f"guestbook.{action}",
        event_id=uuid4().hex,
        target_type="guestbook",
        target_id=entry_id,
        payload={"entry_id": entry_id, "action": action, "reason": reason},
    )
    emit_event(session, event)

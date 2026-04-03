from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.engagement.models import Comment, GuestbookEntry
from aerisun.domain.iam.models import AdminUser

from .common import is_empty


def seed_legacy_guestbook_data(session: Session, *, default_guestbook_entries: list[dict]) -> None:
    if not is_empty(session, GuestbookEntry):
        return
    session.add_all([GuestbookEntry(**item) for item in default_guestbook_entries])


def seed_legacy_comment_data(session: Session, *, default_legacy_comments: list[dict]) -> None:
    if not is_empty(session, Comment):
        return

    inserted_ids: dict[str, str] = {}
    for item in default_legacy_comments:
        parent_key = item.get("parent_key")
        parent_id = inserted_ids.get(str(parent_key)) if parent_key else None
        comment = Comment(
            content_type=str(item["content_type"]),
            content_slug=str(item["content_slug"]),
            parent_id=parent_id,
            author_name=str(item["author_name"]),
            author_email=str(item["author_email"]) if item.get("author_email") is not None else None,
            body=str(item["body"]),
            status=str(item["status"]),
            created_at=item["created_at"],  # type: ignore[arg-type]
            updated_at=item["created_at"],  # type: ignore[arg-type]
        )
        session.add(comment)
        session.flush()
        inserted_ids[str(item["key"])] = comment.id


def seed_dev_admin(session: Session) -> None:
    settings = get_settings()
    if settings.environment != "development":
        return
    if not is_empty(session, AdminUser):
        return
    password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    session.add(AdminUser(username="admin", password_hash=password_hash))

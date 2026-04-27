from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry

migration_key = "2026_04_public_title_identity_backfill_v1"
schema_revision = "0002_public_title_identity"
summary = "回填公开内容的稳定标题和首次公开时间"
mode = "blocking"
resource_keys: tuple[str, ...] = ()


def apply(session: Session) -> None:
    for model in (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry):
        rows = (
            session.query(model)
            .filter(model.status == "published", model.visibility == "public")
            .filter((model.public_title.is_(None)) | (model.first_published_at.is_(None)))
            .all()
        )
        for item in rows:
            if item.public_title is None:
                item.public_title = item.title
            if item.first_published_at is None:
                item.first_published_at = item.published_at or item.created_at
            if item.published_at is None:
                item.published_at = item.first_published_at
            session.add(item)

        archived_rows = (
            session.query(model)
            .filter(model.status == "archived", model.visibility == "private")
            .filter(model.first_archived_at.is_(None))
            .all()
        )
        for item in archived_rows:
            item.first_archived_at = item.published_at or item.created_at
            if item.published_at is None:
                item.published_at = item.first_archived_at
            session.add(item)

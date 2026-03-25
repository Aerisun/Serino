from __future__ import annotations

import io
import json
import zipfile

from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.schemas import ContentAdminRead, ImportResult
from aerisun.domain.exceptions import ValidationError as DomainValidationError

_CONTENT_MODELS = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}

_ALLOWED_FIELDS = {
    "slug",
    "title",
    "summary",
    "body",
    "tags",
    "status",
    "visibility",
    "published_at",
    "category",
    "view_count",
    "mood",
    "weather",
    "poem",
    "author_name",
    "source",
    "is_pinned",
    "pin_order",
}


def export_content_json(session: Session, content_type: str) -> list[dict]:
    """Export content as list of dicts. Raises ValueError for invalid type."""
    model = _CONTENT_MODELS.get(content_type)
    if not model:
        raise DomainValidationError(f"Invalid content_type: {content_type}")
    items = session.query(model).order_by(model.created_at.desc()).all()
    return [ContentAdminRead.model_validate(item).model_dump(mode="json") for item in items]


def export_content_markdown_zip(session: Session, content_type: str) -> bytes:
    """Export content as Markdown ZIP bytes. Raises ValueError for invalid type."""
    model = _CONTENT_MODELS.get(content_type)
    if not model:
        raise DomainValidationError(f"Invalid content_type: {content_type}")
    items = session.query(model).order_by(model.created_at.desc()).all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            front = (
                f"---\ntitle: {item.title}\nslug: {item.slug}\n"
                f"status: {item.status}\ntags: {json.dumps(item.tags or [])}\n"
                f"created_at: {item.created_at.isoformat() if item.created_at else ''}\n---\n\n"
            )
            content = front + (item.body or "")
            zf.writestr(f"{item.slug}.md", content)
    buf.seek(0)
    return buf.getvalue()


def import_content_json(session: Session, content_type: str, data: list[dict]) -> ImportResult:
    """Import content from JSON data. Raises ValueError for invalid type."""
    model = _CONTENT_MODELS.get(content_type)
    if not model:
        raise DomainValidationError(f"Invalid content_type: {content_type}")

    result = ImportResult()
    for entry in data:
        slug = entry.get("slug")
        if not slug:
            result.errors.append(f"Missing slug in entry: {entry.get('title', 'unknown')}")
            continue

        existing = session.query(model).filter(model.slug == slug).first()
        filtered = {k: v for k, v in entry.items() if k in _ALLOWED_FIELDS}

        if existing:
            for k, v in filtered.items():
                if k != "slug":
                    setattr(existing, k, v)
            result.updated += 1
        else:
            obj = model(**filtered)
            session.add(obj)
            result.created += 1

    session.commit()
    return result

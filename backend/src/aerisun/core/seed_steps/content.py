from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.domain.site_config.models import PageCopy, PageDisplayOption


def seed_content_entries(session: Session, model, entries: list[dict]) -> None:  # type: ignore[no-untyped-def]
    existing_slugs = set(session.scalars(select(model.slug)).all())
    missing_entries = [entry for entry in entries if entry["slug"] not in existing_slugs]
    if missing_entries:
        session.add_all([model(**entry) for entry in missing_entries])


def merge_page_copy(existing: PageCopy, default_item: dict) -> bool:
    changed = False
    scalar_fields = (
        "label",
        "nav_label",
        "title",
        "subtitle",
        "description",
        "search_placeholder",
        "empty_message",
        "max_width",
        "page_size",
        "download_label",
    )
    for field in scalar_fields:
        current_value = getattr(existing, field)
        default_value = default_item.get(field)
        if current_value is None and default_value is not None:
            setattr(existing, field, default_value)
            changed = True

    default_extras = default_item.get("extras") or {}
    existing_extras = dict(existing.extras or {})
    for key, value in default_extras.items():
        if key not in existing_extras or existing_extras[key] in (None, ""):
            existing_extras[key] = value
            changed = True

    if existing.page_key == "calendar" and existing_extras.get("weekdayLabels") == [
        "周日",
        "周一",
        "周二",
        "周三",
        "周四",
        "周五",
        "周六",
    ]:
        existing_extras["weekdayLabels"] = default_extras.get("weekdayLabels", existing_extras["weekdayLabels"])
        changed = True

    if existing.page_key == "notFound" and existing_extras.get("badgeLabel") == "Shell mismatch":
        existing_extras["badgeLabel"] = default_extras.get("badgeLabel", "404")
        changed = True

    if changed:
        existing.extras = existing_extras
    return changed


def seed_missing_page_options(session: Session, default_page_options: list[dict], existing_keys: set[str]) -> None:
    missing_items = [item for item in default_page_options if item["page_key"] not in existing_keys]
    if missing_items:
        session.add_all([PageDisplayOption(**item) for item in missing_items])


def seed_missing_page_copies(session: Session, default_page_copies: list[dict]) -> None:
    existing_by_key = {page_copy.page_key: page_copy for page_copy in session.scalars(select(PageCopy)).all()}

    for item in default_page_copies:
        page_copy = existing_by_key.get(item["page_key"])
        if page_copy is None:
            session.add(PageCopy(**item))
            continue
        merge_page_copy(page_copy, item)

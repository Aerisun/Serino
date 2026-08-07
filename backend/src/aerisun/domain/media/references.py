from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import JSON, String, Text, inspect, select, text
from sqlalchemy.orm import Session

from aerisun.domain.automation.models import AgentRun
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Comment, GuestbookEntry
from aerisun.domain.media.paths import AssetScope
from aerisun.domain.ops.models import AuditLog, ConfigRevision
from aerisun.domain.site_config.models import PageCopy, ResumeBasics, SiteProfile
from aerisun.domain.subscription.models import ContentNotification

ARTICLE_CATEGORY_PRIORITY = ("post", "diary", "thought", "excerpt", "resume", "friends")
_VISITOR_CATEGORY_PRIORITY = ("guestbook", "comment")
_URL_BOUNDARY = r"(?=$|[^A-Za-z0-9._~:/%=-])"


@dataclass(frozen=True, slots=True)
class RewriteResult[ValueT]:
    value: ValueT
    replacement_count: int


class AssetClassification(BaseModel):
    scope: AssetScope
    category: str
    usages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReferenceField:
    model: type[Any]
    column: str
    value_kind: Literal["text", "json"]
    usage: str | None = None
    usage_resolver: Callable[[Any], str | None] | None = None

    @property
    def table(self) -> str:
        return str(self.model.__table__.name)

    def usage_for(self, row: Any) -> str | None:
        if self.usage_resolver is not None:
            return self.usage_resolver(row)
        return self.usage


@dataclass(frozen=True, slots=True)
class AssetReference:
    asset_id: str
    table: str
    column: str
    row_id: str
    usage: str | None
    matched_url: str
    occurrence_count: int


@dataclass(frozen=True, slots=True)
class UnhandledReference:
    table: str
    column: str
    row_id: str
    matched_url: str
    occurrence_count: int


def _page_copy_usage(row: PageCopy) -> str | None:
    return "friends" if row.page_key == "friends" else None


REFERENCE_FIELDS: tuple[ReferenceField, ...] = (
    ReferenceField(PostEntry, "body", "text", "post"),
    ReferenceField(PostEntry, "summary", "text", "post"),
    ReferenceField(DiaryEntry, "body", "text", "diary"),
    ReferenceField(DiaryEntry, "summary", "text", "diary"),
    ReferenceField(DiaryEntry, "poem", "text", "diary"),
    ReferenceField(ThoughtEntry, "body", "text", "thought"),
    ReferenceField(ThoughtEntry, "summary", "text", "thought"),
    ReferenceField(ExcerptEntry, "body", "text", "excerpt"),
    ReferenceField(ExcerptEntry, "summary", "text", "excerpt"),
    ReferenceField(ResumeBasics, "summary", "text", "resume"),
    ReferenceField(ResumeBasics, "profile_image_url", "text", "system:resume-avatar"),
    ReferenceField(PageCopy, "extras", "json", usage_resolver=_page_copy_usage),
    ReferenceField(Comment, "body", "text", "comment"),
    ReferenceField(GuestbookEntry, "body", "text", "guestbook"),
    ReferenceField(SiteProfile, "og_image", "text", "system:site-og"),
    ReferenceField(SiteProfile, "site_icon_url", "text", "system:site-icon"),
    ReferenceField(SiteProfile, "hero_image_url", "text", "system:hero-image"),
    ReferenceField(SiteProfile, "hero_poster_url", "text", "system:hero-poster"),
    ReferenceField(SiteProfile, "hero_video_url", "text", "system:hero-video"),
    ReferenceField(SiteProfile, "hero_actions", "text", "system:hero-actions"),
    ReferenceField(ConfigRevision, "before_snapshot", "json"),
    ReferenceField(ConfigRevision, "after_snapshot", "json"),
    ReferenceField(ConfigRevision, "before_preview", "json"),
    ReferenceField(ConfigRevision, "after_preview", "json"),
    ReferenceField(AuditLog, "payload", "json"),
    ReferenceField(ContentNotification, "content_summary", "text"),
    ReferenceField(AgentRun, "input_payload", "json"),
    ReferenceField(AgentRun, "context_payload", "json"),
    ReferenceField(AgentRun, "result_payload", "json"),
)

ACTIVE_REFERENCE_FIELDS: tuple[ReferenceField, ...] = tuple(
    field for field in REFERENCE_FIELDS if field.model not in {ConfigRevision, ContentNotification, AgentRun}
)

_NON_CONTENT_MEDIA_METADATA_FIELDS = {
    ("assets", "resource_key"),
    ("assets", "storage_path"),
    ("assets", "remote_object_key"),
    ("asset_mirror_queue_items", "object_key"),
    ("asset_local_delete_queue_items", "storage_path"),
    ("asset_remote_delete_queue_items", "object_key"),
    ("asset_remote_upload_queue_items", "object_key"),
}


def _replacement_pattern(replacements: Mapping[str, str]) -> re.Pattern[str] | None:
    source_values = sorted((value for value in replacements if value), key=lambda value: (-len(value), value))
    if not source_values:
        return None
    alternatives = "|".join(re.escape(value) for value in source_values)
    return re.compile(f"(?:{alternatives}){_URL_BOUNDARY}")


@lru_cache(maxsize=8)
def _legacy_url_pattern(legacy_urls: tuple[str, ...]) -> re.Pattern[str] | None:
    return _replacement_pattern({url: url for url in legacy_urls})


def rewrite_text(value: str, replacements: Mapping[str, str]) -> RewriteResult[str]:
    pattern = _replacement_pattern(replacements)
    return _rewrite_text_with_pattern(value, replacements, pattern)


def _rewrite_text_with_pattern(
    value: str,
    replacements: Mapping[str, str],
    pattern: re.Pattern[str] | None,
) -> RewriteResult[str]:
    if pattern is None or not value:
        return RewriteResult(value=value, replacement_count=0)

    rewritten, count = pattern.subn(lambda match: replacements[match.group(0)], value)
    return RewriteResult(value=rewritten, replacement_count=count)


def rewrite_json_value(value: Any, replacements: Mapping[str, str]) -> RewriteResult[Any]:
    return _rewrite_json_value_with_pattern(value, replacements, _replacement_pattern(replacements))


def _rewrite_json_value_with_pattern(
    value: Any,
    replacements: Mapping[str, str],
    pattern: re.Pattern[str] | None,
) -> RewriteResult[Any]:
    if isinstance(value, str):
        return _rewrite_text_with_pattern(value, replacements, pattern)
    if isinstance(value, list):
        rewritten_items: list[Any] = []
        total = 0
        for item in value:
            result = _rewrite_json_value_with_pattern(item, replacements, pattern)
            rewritten_items.append(result.value)
            total += result.replacement_count
        return RewriteResult(value=rewritten_items, replacement_count=total)
    if isinstance(value, tuple):
        rewritten_items = []
        total = 0
        for item in value:
            result = _rewrite_json_value_with_pattern(item, replacements, pattern)
            rewritten_items.append(result.value)
            total += result.replacement_count
        return RewriteResult(value=tuple(rewritten_items), replacement_count=total)
    if isinstance(value, dict):
        rewritten_mapping: dict[Any, Any] = {}
        total = 0
        for key, item in value.items():
            result = _rewrite_json_value_with_pattern(item, replacements, pattern)
            rewritten_mapping[key] = result.value
            total += result.replacement_count
        return RewriteResult(value=rewritten_mapping, replacement_count=total)
    return RewriteResult(value=value, replacement_count=0)


def _url_counts_with_pattern(value: Any, pattern: re.Pattern[str] | None) -> dict[str, int]:
    if pattern is None:
        return {}
    if isinstance(value, str):
        counts: dict[str, int] = {}
        for match in pattern.finditer(value):
            matched = match.group(0)
            counts[matched] = counts.get(matched, 0) + 1
        return counts
    if isinstance(value, (list, tuple)):
        counts: dict[str, int] = {}
        for item in value:
            for matched, count in _url_counts_with_pattern(item, pattern).items():
                counts[matched] = counts.get(matched, 0) + count
        return counts
    if isinstance(value, dict):
        counts = {}
        for item in value.values():
            for matched, count in _url_counts_with_pattern(item, pattern).items():
                counts[matched] = counts.get(matched, 0) + count
        return counts
    return {}


def find_legacy_url_counts(value: Any, legacy_urls: Set[str]) -> dict[str, int]:
    pattern = _legacy_url_pattern(tuple(sorted(legacy_urls)))
    return _url_counts_with_pattern(value, pattern)


def collect_registered_references(
    session: Session,
    legacy_url_to_asset_id: Mapping[str, str],
    *,
    fields: Sequence[ReferenceField] = REFERENCE_FIELDS,
) -> list[AssetReference]:
    legacy_urls = set(legacy_url_to_asset_id)
    pattern = _replacement_pattern({url: url for url in legacy_urls})
    references: list[AssetReference] = []
    for field in fields:
        rows = session.scalars(select(field.model)).all()
        for row in rows:
            value = getattr(row, field.column)
            for matched_url, count in _url_counts_with_pattern(value, pattern).items():
                references.append(
                    AssetReference(
                        asset_id=legacy_url_to_asset_id[matched_url],
                        table=field.table,
                        column=field.column,
                        row_id=str(row.id),
                        usage=field.usage_for(row),
                        matched_url=matched_url,
                        occurrence_count=count,
                    )
                )
    references.sort(key=lambda item: (item.asset_id, item.table, item.column, item.row_id, item.matched_url))
    return references


def rewrite_registered_references(session: Session, replacements: Mapping[str, str]) -> int:
    total = 0
    pattern = _replacement_pattern(replacements)
    for field in REFERENCE_FIELDS:
        rows = session.scalars(select(field.model)).all()
        for row in rows:
            current_value = getattr(row, field.column)
            if field.value_kind == "json":
                result = _rewrite_json_value_with_pattern(current_value, replacements, pattern)
            else:
                result = (
                    _rewrite_text_with_pattern(current_value, replacements, pattern)
                    if isinstance(current_value, str)
                    else None
                )
            if result is None or result.replacement_count == 0:
                continue
            setattr(row, field.column, result.value)
            total += result.replacement_count
    session.flush()
    return total


def scan_unhandled_legacy_references(
    session: Session,
    legacy_urls: Set[str],
) -> list[UnhandledReference]:
    if not legacy_urls:
        return []
    bind = session.get_bind()
    inspector = inspect(bind)
    registered = {(field.table, field.column) for field in REFERENCE_FIELDS} | _NON_CONTENT_MEDIA_METADATA_FIELDS
    quote = bind.dialect.identifier_preparer.quote
    pattern = _replacement_pattern({url: url for url in legacy_urls})
    unhandled: list[UnhandledReference] = []

    for table_name in sorted(inspector.get_table_names()):
        columns = inspector.get_columns(table_name)
        primary_keys = list(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
        if not primary_keys:
            if any(column["name"] == "id" for column in columns):
                primary_keys = ["id"]
            else:
                continue
        candidate_columns = [
            column
            for column in columns
            if isinstance(column["type"], (String, Text, JSON)) and (table_name, str(column["name"])) not in registered
        ]
        if not candidate_columns:
            continue

        selected_names = [*primary_keys, *(str(column["name"]) for column in candidate_columns)]
        statement = text(f"SELECT {', '.join(quote(name) for name in selected_names)} FROM {quote(table_name)}")
        for row in session.execute(statement).mappings():
            row_id = ":".join(str(row[name]) for name in primary_keys)
            for column in candidate_columns:
                column_name = str(column["name"])
                for matched_url, count in _url_counts_with_pattern(row[column_name], pattern).items():
                    unhandled.append(
                        UnhandledReference(
                            table=table_name,
                            column=column_name,
                            row_id=row_id,
                            matched_url=matched_url,
                            occurrence_count=count,
                        )
                    )
    unhandled.sort(key=lambda item: (item.table, item.column, item.row_id, item.matched_url))
    return unhandled


def classify_asset_usages(usages: Set[str]) -> AssetClassification:
    normalized = {str(usage).strip().lower() for usage in usages if str(usage).strip()}
    ordered_usages = tuple(sorted(normalized))

    system_categories = sorted(usage.split(":", 1)[1] for usage in normalized if usage.startswith("system:"))
    if system_categories:
        return AssetClassification(scope="system", category=system_categories[0], usages=ordered_usages)

    for category in ARTICLE_CATEGORY_PRIORITY:
        if category in normalized:
            return AssetClassification(scope="article", category=category, usages=ordered_usages)

    for category in _VISITOR_CATEGORY_PRIORITY:
        if category in normalized:
            return AssetClassification(scope="visitor", category=category, usages=ordered_usages)

    return AssetClassification(scope="user", category="general", usages=ordered_usages)


def build_legacy_url_variants(asset: Any, *, site_urls: Sequence[str]) -> tuple[str, ...]:
    resource_key = str(getattr(asset, "resource_key", "") or "").strip().lstrip("/")
    keys: list[str] = []
    if resource_key.startswith("internal/"):
        suffix = resource_key[len("internal/") :]
        keys.extend((resource_key, f"public/{suffix}"))
    elif resource_key.startswith("public/"):
        suffix = resource_key[len("public/") :]
        keys.extend((resource_key, f"internal/{suffix}"))
    elif resource_key:
        keys.append(resource_key)

    paths = [f"/media/{key}" for key in keys]
    public_slug = str(getattr(asset, "public_slug", "") or "").strip().lstrip("/")
    if public_slug and "/" not in public_slug:
        paths.append(f"/media/{public_slug}")

    variants: list[str] = []
    for path in paths:
        if path not in variants:
            variants.append(path)
    for site_url in site_urls:
        base = str(site_url or "").strip().rstrip("/")
        if not base:
            continue
        for path in paths:
            absolute = f"{base}{path}"
            if absolute not in variants:
                variants.append(absolute)
    return tuple(variants)

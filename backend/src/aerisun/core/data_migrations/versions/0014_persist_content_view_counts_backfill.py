from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.ops import repository as ops_repo
from aerisun.domain.waline.service import build_comment_path, get_counter_stats_by_urls

migration_key = "2026_07_persist_content_view_counts_v1"
schema_revision = "0014_persist_content_view_counts"
summary = "将已有内容浏览量写入持久累计值"
mode = "blocking"
resource_keys: tuple[str, ...] = ()


def apply(session: Session) -> None:
    for content_type, model in (
        ("posts", PostEntry),
        ("diary", DiaryEntry),
        ("thoughts", ThoughtEntry),
        ("excerpts", ExcerptEntry),
    ):
        items = session.query(model).all()
        paths_by_slug = {item.slug: build_comment_path(content_type, item.slug) for item in items}
        paths = list(paths_by_slug.values())
        waline_stats = get_counter_stats_by_urls(urls=paths)
        visit_counts = ops_repo.count_successful_visit_records_by_paths(session, paths=paths)

        for item in items:
            path = paths_by_slug[item.slug]
            waline_views = waline_stats.get(path).pageview_count if path in waline_stats else 0
            recorded_visits = visit_counts.get(path, 0)
            view_count = max(int(item.view_count or 0), waline_views, recorded_visits)
            if view_count == item.view_count:
                continue
            session.execute(
                update(model)
                .where(model.id == item.id)
                .values(
                    view_count=view_count,
                    updated_at=model.updated_at,
                ),
            )

"""Add manuscript and note page defaults.

Revision ID: 0026_manuscript_note_page_config
Revises: 0025_post_manuscript_note_kind
Create Date: 2026-08-18
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0026_manuscript_note_page_config"
down_revision = "0025_post_manuscript_note_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    now = datetime.now(UTC)

    if "page_copy" in tables:
        page_copy = sa.table(
            "page_copy",
            sa.column("id", sa.String),
            sa.column("page_key", sa.String),
            sa.column("title", sa.String),
            sa.column("subtitle", sa.Text),
            sa.column("search_placeholder", sa.String),
            sa.column("empty_message", sa.Text),
            sa.column("max_width", sa.String),
            sa.column("page_size", sa.Integer),
            sa.column("extras", sa.JSON),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        bind.execute(
            page_copy.update()
            .where(page_copy.c.page_key == "posts")
            .values(
                title="文稿",
                subtitle="让思考与经历，在文字中缓缓流淌",
                search_placeholder="搜索文稿...",
                empty_message="没有找到匹配的文稿",
                updated_at=now,
            )
        )
        has_notes = bind.execute(
            sa.select(page_copy.c.id).where(page_copy.c.page_key == "notes").limit(1)
        ).scalar()
        if has_notes is None:
            bind.execute(
                page_copy.insert().values(
                    id=str(uuid4()),
                    page_key="notes",
                    title="手记",
                    subtitle="拾起日常微光，记下心绪流转",
                    search_placeholder="搜索手记...",
                    empty_message="没有找到匹配的手记",
                    max_width="max-w-4xl",
                    page_size=15,
                    extras={
                        "category_all_label": "全部",
                        "category_fallback_label": "未分类",
                        "errorTitle": "手记加载失败",
                        "retryLabel": "重试",
                        "loadMoreLabel": "加载更多...",
                        "detailBackLabel": "返回",
                        "detailListLabel": "返回列表",
                        "detailMissingTitle": "手记不存在",
                        "detailMissingDescription": "你访问的手记暂时不存在。",
                        "detailEndLabel": "— END —",
                    },
                    created_at=now,
                    updated_at=now,
                )
            )

    if not {"nav_items", "site_profile"} <= tables:
        return

    nav_items = sa.table(
        "nav_items",
        sa.column("id", sa.String),
        sa.column("site_profile_id", sa.String),
        sa.column("parent_id", sa.String),
        sa.column("label", sa.String),
        sa.column("href", sa.String),
        sa.column("page_key", sa.String),
        sa.column("trigger", sa.String),
        sa.column("order_index", sa.Integer),
        sa.column("is_enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    site_profile = sa.table("site_profile", sa.column("id", sa.String))

    bind.execute(
        nav_items.update()
        .where(sa.or_(nav_items.c.page_key == "posts", nav_items.c.href == "/posts"))
        .values(label="文稿", page_key="posts", updated_at=now)
    )

    for site_id in bind.execute(sa.select(site_profile.c.id)).scalars():
        has_notes = bind.execute(
            sa.select(nav_items.c.id)
            .where(
                nav_items.c.site_profile_id == site_id,
                sa.or_(nav_items.c.page_key == "notes", nav_items.c.href == "/notes"),
            )
            .limit(1)
        ).scalar()
        if has_notes is not None:
            continue

        post_order = bind.execute(
            sa.select(nav_items.c.order_index)
            .where(
                nav_items.c.site_profile_id == site_id,
                nav_items.c.parent_id.is_(None),
                sa.or_(nav_items.c.page_key == "posts", nav_items.c.href == "/posts"),
            )
            .order_by(nav_items.c.order_index.asc())
            .limit(1)
        ).scalar()
        note_order = int(post_order) + 1 if post_order is not None else 1
        bind.execute(
            nav_items.update()
            .where(
                nav_items.c.site_profile_id == site_id,
                nav_items.c.parent_id.is_(None),
                nav_items.c.order_index >= note_order,
            )
            .values(order_index=nav_items.c.order_index + 1, updated_at=now)
        )
        bind.execute(
            nav_items.insert().values(
                id=str(uuid4()),
                site_profile_id=site_id,
                parent_id=None,
                label="手记",
                href="/notes",
                page_key="notes",
                trigger="none",
                order_index=note_order,
                is_enabled=True,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    # Page copy and navigation are user-editable data; preserve them on downgrade.
    pass

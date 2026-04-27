from __future__ import annotations

from datetime import date, datetime

import pytest

from aerisun.core.db import get_session_factory
from aerisun.core.time import BEIJING_TZ
from aerisun.domain.content import service as content_service
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, ThoughtEntry

BASE = "/api/v1/admin/content/default-title"


@pytest.mark.parametrize(
    ("content_type", "prefix"),
    [
        ("diary", "日记"),
        ("thoughts", "碎碎念"),
        ("excerpts", "文摘"),
    ],
)
def test_default_title_endpoint_formats_title(
    client, admin_headers, monkeypatch, content_type: str, prefix: str
) -> None:
    monkeypatch.setattr(content_service, "beijing_today", lambda: date(2026, 4, 5))

    params = {"content_type": content_type}
    if content_type != "diary":
        params["status"] = "draft"

    response = client.get(
        BASE,
        params=params,
        headers=admin_headers,
    )

    assert response.status_code == 200
    if content_type == "diary":
        assert response.json() == {
            "title": "26年4月5日记",
            "sequence": 1,
            "date_label": "26年4月5日",
        }
    else:
        assert response.json() == {
            "title": f"{prefix}一则 (26.4.5.)-草稿",
            "sequence": 1,
            "date_label": "26.4.5.",
        }


@pytest.mark.parametrize(
    ("content_type", "route_prefix", "model", "prefix", "category_a", "category_b"),
    [
        ("diary", "/api/v1/admin/diary/", DiaryEntry, "日记", None, None),
        ("thoughts", "/api/v1/admin/thoughts/", ThoughtEntry, "碎碎念", "生活", "工作"),
        ("excerpts", "/api/v1/admin/excerpts/", ExcerptEntry, "文摘", "文学", "哲学"),
    ],
)
def test_default_title_endpoint_counts_draft_published_and_archived_entries(
    client,
    admin_headers,
    monkeypatch,
    content_type: str,
    route_prefix: str,
    model,
    prefix: str,
    category_a: str | None,
    category_b: str | None,
) -> None:
    monkeypatch.setattr(content_service, "beijing_today", lambda: date(2026, 4, 5))

    published_payload = {
        "slug": f"{content_type}-default-title-published",
        "title": f"已发布{prefix}",
        "body": f"published {content_type}",
        "status": "published",
        "visibility": "public",
        "published_at": "2026-04-05T09:00:00+08:00",
        "category": category_a,
    }
    archived_payload = {
        "slug": f"{content_type}-default-title-archived",
        "title": f"已归档{prefix}",
        "body": f"archived {content_type}",
        "status": "published",
        "visibility": "private",
        "category": category_a,
    }
    draft_payload = {
        "slug": f"{content_type}-default-title-draft",
        "title": f"草稿{prefix}",
        "body": f"draft {content_type}",
        "status": "draft",
        "visibility": "private",
        "category": category_a,
    }

    first_response = client.post(route_prefix, json=published_payload, headers=admin_headers)
    second_response = client.post(route_prefix, json=archived_payload, headers=admin_headers)
    draft_response = client.post(route_prefix, json=draft_payload, headers=admin_headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert draft_response.status_code == 201

    second_id = second_response.json()["id"]
    draft_id = draft_response.json()["id"]
    session_factory = get_session_factory()
    with session_factory() as session:
        archived_entry = session.query(model).filter(model.id == second_id).one()
        draft_entry = session.query(model).filter(model.id == draft_id).one()
        archived_entry.published_at = None
        archived_entry.created_at = datetime(2026, 4, 5, 2, 0, tzinfo=BEIJING_TZ)
        draft_entry.published_at = None
        draft_entry.created_at = datetime(2026, 4, 5, 3, 0, tzinfo=BEIJING_TZ)
        session.commit()

    response = client.get(
        BASE,
        params={
            "content_type": content_type,
            "category": category_a,
            "status": "published",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    if content_type == "diary":
        assert response.json() == {
            "title": "26年4月5日记",
            "sequence": 1,
            "date_label": "26年4月5日",
        }
    else:
        assert response.json() == {
            "title": f"{prefix}一则 (26.4.5.)",
            "sequence": 1,
            "date_label": "26.4.5.",
        }

    if content_type != "diary" and category_b:
        other_category_response = client.get(
            BASE,
            params={
                "content_type": content_type,
                "category": category_b,
                "status": "archived",
            },
            headers=admin_headers,
        )
        assert other_category_response.status_code == 200
        assert other_category_response.json() == {
            "title": f"{prefix}一则 (26.4.5.)-归档",
            "sequence": 1,
            "date_label": "26.4.5.",
        }


@pytest.mark.parametrize(
    ("content_type", "route_prefix", "model", "prefix"),
    [
        ("thoughts", "/api/v1/admin/thoughts/", ThoughtEntry, "碎碎念"),
        ("excerpts", "/api/v1/admin/excerpts/", ExcerptEntry, "文摘"),
    ],
)
def test_public_default_title_uses_public_pool_only_and_ignores_category(
    client,
    admin_headers,
    monkeypatch,
    content_type: str,
    route_prefix: str,
    model,
    prefix: str,
) -> None:
    monkeypatch.setattr(content_service, "beijing_today", lambda: date(2026, 4, 5))

    draft_response = client.post(
        route_prefix,
        json={
            "slug": f"{content_type}-public-pool-draft",
            "title": f"{prefix}一则 (26.4.5.)-草稿",
            "body": "draft should not count",
            "status": "draft",
            "visibility": "private",
            "category": "生活",
        },
        headers=admin_headers,
    )
    archived_response = client.post(
        route_prefix,
        json={
            "slug": f"{content_type}-public-pool-archived",
            "title": f"{prefix}二则 (26.4.5.)-归档",
            "body": "archived should not count",
            "status": "published",
            "visibility": "private",
            "category": "生活",
        },
        headers=admin_headers,
    )
    public_response = client.post(
        route_prefix,
        json={
            "slug": f"{content_type}-public-pool-public",
            "title": f"{prefix}一则 (26.4.5.)",
            "body": "public should count",
            "status": "published",
            "visibility": "public",
            "published_at": "2026-04-05T09:00:00+08:00",
            "category": "生活",
        },
        headers=admin_headers,
    )

    assert draft_response.status_code == 201
    assert archived_response.status_code == 201
    assert public_response.status_code == 201
    session_factory = get_session_factory()
    with session_factory() as session:
        for item in session.query(model).filter(
            model.slug.in_(
                [
                    f"{content_type}-public-pool-draft",
                    f"{content_type}-public-pool-archived",
                    f"{content_type}-public-pool-public",
                ]
            )
        ):
            item.created_at = datetime(2026, 4, 5, 3, 0, tzinfo=BEIJING_TZ)
        session.commit()

    response = client.get(
        BASE,
        params={
            "content_type": content_type,
            "category": "工作",
            "status": "published",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": f"{prefix}二则 (26.4.5.)",
        "sequence": 2,
        "date_label": "26.4.5.",
    }


@pytest.mark.parametrize(
    ("content_type", "route_prefix", "prefix", "category"),
    [
        ("thoughts", "/api/v1/admin/thoughts/", "碎碎念", "日常"),
        ("excerpts", "/api/v1/admin/excerpts/", "文摘", "摘录"),
    ],
)
def test_default_title_endpoint_excludes_current_item_from_sequence(
    client,
    admin_headers,
    monkeypatch,
    content_type: str,
    route_prefix: str,
    prefix: str,
    category: str,
) -> None:
    monkeypatch.setattr(content_service, "beijing_today", lambda: date(2026, 4, 5))

    create_response = client.post(
        route_prefix,
        json={
            "slug": f"{content_type}-default-title-existing",
            "title": f"{prefix}一则 (26.4.5.)-草稿",
            "body": f"existing {content_type}",
            "status": "draft",
            "visibility": "private",
            "category": category,
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 201
    item_id = create_response.json()["id"]
    session_factory = get_session_factory()
    with session_factory() as session:
        item = session.query(content_service.repo.CONTENT_MODELS[content_type]).filter_by(id=item_id).one()
        item.created_at = datetime(2026, 4, 5, 11, 0, tzinfo=BEIJING_TZ)
        session.commit()

    response = client.get(
        BASE,
        params={
            "content_type": content_type,
            "category": category,
            "status": "published",
            "item_id": item_id,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": f"{prefix}一则 (26.4.5.)",
        "sequence": 1,
        "date_label": "26.4.5.",
    }

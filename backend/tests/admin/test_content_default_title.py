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

    response = client.get(
        BASE,
        params={"content_type": content_type},
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


@pytest.mark.parametrize(
    ("content_type", "route_prefix", "model", "prefix", "category_a", "category_b"),
    [
        ("diary", "/api/v1/admin/diary/", DiaryEntry, "日记", None, None),
        ("thoughts", "/api/v1/admin/thoughts/", ThoughtEntry, "碎碎念", "生活", "工作"),
        ("excerpts", "/api/v1/admin/excerpts/", ExcerptEntry, "文摘", "文学", "哲学"),
    ],
)
def test_default_title_endpoint_counts_same_day_entries_by_category(
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

    payloads = [
        {
            "slug": f"{content_type}-default-title-public",
            "title": f"公开{prefix}",
            "body": f"public {content_type}",
            "visibility": "public",
            "published_at": "2026-04-05T09:00:00+08:00",
            "category": category_a,
        },
        {
            "slug": f"{content_type}-default-title-private",
            "title": f"私密{prefix}",
            "body": f"private {content_type}",
            "visibility": "private",
            "category": category_a,
        },
        {
            "slug": f"{content_type}-default-title-other",
            "title": f"其他{prefix}",
            "body": f"other {content_type}",
            "visibility": "private",
            "category": category_b,
        },
    ]

    created_ids: list[str] = []
    for payload in payloads:
        response = client.post(route_prefix, json=payload, headers=admin_headers)
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    session_factory = get_session_factory()
    with session_factory() as session:
        for index, item_id in enumerate(created_ids):
            item = session.query(model).filter(model.id == item_id).one()
            item.published_at = item.published_at
            item.created_at = datetime(2026, 4, 5, 2 + index, 0, tzinfo=BEIJING_TZ)
        session.commit()

    response = client.get(
        BASE,
        params={
            "content_type": content_type,
            "category": category_a,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    if content_type == "diary":
        assert response.json() == {
            "title": "26年4月5日记",
            "sequence": 4,
            "date_label": "26年4月5日",
        }
    else:
        assert response.json() == {
            "title": f"{prefix}三则 (26.4.5.)",
            "sequence": 3,
            "date_label": "26.4.5.",
        }

    if content_type != "diary" and category_b:
        other_category_response = client.get(
            BASE,
            params={
                "content_type": content_type,
                "category": category_b,
            },
            headers=admin_headers,
        )
        assert other_category_response.status_code == 200
        assert other_category_response.json() == {
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
            "title": f"{prefix}一则 (26.4.5.)",
            "body": f"existing {content_type}",
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

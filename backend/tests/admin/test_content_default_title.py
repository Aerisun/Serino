from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from aerisun.core.db import get_session_factory
from aerisun.domain.content import service as content_service
from aerisun.domain.content.models import ThoughtEntry

BASE = "/api/v1/admin/content/default-title"


@pytest.mark.parametrize(
    ("content_type", "prefix"),
    [
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
    assert response.json() == {
        "title": f"{prefix}一则 (26.4.5.)",
        "sequence": 1,
        "date_label": "26.4.5.",
    }


def test_default_title_endpoint_counts_published_and_archived_entries(client, admin_headers, monkeypatch) -> None:
    monkeypatch.setattr(content_service, "beijing_today", lambda: date(2026, 4, 5))

    published_payload = {
        "slug": "thought-default-title-published",
        "title": "已发布碎碎念",
        "body": "published thought",
        "status": "published",
        "visibility": "public",
        "published_at": "2026-04-05T09:00:00+08:00",
    }
    archived_payload = {
        "slug": "thought-default-title-archived",
        "title": "已归档碎碎念",
        "body": "archived thought",
        "status": "published",
        "visibility": "private",
    }
    draft_payload = {
        "slug": "thought-default-title-draft",
        "title": "草稿碎碎念",
        "body": "draft thought",
        "status": "draft",
        "visibility": "private",
    }

    first_response = client.post("/api/v1/admin/thoughts/", json=published_payload, headers=admin_headers)
    second_response = client.post("/api/v1/admin/thoughts/", json=archived_payload, headers=admin_headers)
    draft_response = client.post("/api/v1/admin/thoughts/", json=draft_payload, headers=admin_headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert draft_response.status_code == 201

    second_id = second_response.json()["id"]
    session_factory = get_session_factory()
    with session_factory() as session:
        archived_entry = session.query(ThoughtEntry).filter(ThoughtEntry.id == second_id).one()
        archived_entry.published_at = None
        archived_entry.created_at = datetime(2026, 4, 4, 18, 0, tzinfo=UTC)
        session.commit()

    response = client.get(
        BASE,
        params={"content_type": "thoughts"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "碎碎念三则 (26.4.5.)",
        "sequence": 3,
        "date_label": "26.4.5.",
    }

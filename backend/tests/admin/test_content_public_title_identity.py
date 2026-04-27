from __future__ import annotations

from datetime import datetime

from aerisun.core.db import get_session_factory
from aerisun.core.time import BEIJING_TZ, to_beijing_datetime
from aerisun.domain.content import service as content_service
from aerisun.domain.content.models import ThoughtEntry

ADMIN_BASE = "/api/v1/admin/thoughts"


def _thought_payload(slug: str, title: str, *, status: str = "draft", visibility: str = "private") -> dict:
    return {
        "slug": slug,
        "title": title,
        "body": f"body for {slug}",
        "status": status,
        "visibility": visibility,
    }


def _get_thought(slug: str) -> ThoughtEntry:
    with get_session_factory()() as session:
        return session.query(ThoughtEntry).filter(ThoughtEntry.slug == slug).one()


def _beijing(value: datetime | None) -> datetime | None:
    return None if value is None else to_beijing_datetime(value)


def test_first_public_title_ignores_draft_numbers(client, admin_headers) -> None:
    first_id = ""
    for index in range(1, 4):
        response = client.post(
            f"{ADMIN_BASE}/",
            json=_thought_payload(
                f"public-title-draft-{index}",
                f"碎碎念{['', '一', '二', '三'][index]}则 (26.4.26.)-草稿",
            ),
            headers=admin_headers,
        )
        assert response.status_code == 201
        if not first_id:
            first_id = response.json()["id"]

    publish_response = client.put(
        f"{ADMIN_BASE}/{first_id}",
        json={
            "status": "published",
            "visibility": "public",
            "published_at": "2026-04-26T10:00:00+08:00",
        },
        headers=admin_headers,
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["title"] == "碎碎念一则 (26.4.26.)"
    item = _get_thought(publish_response.json()["slug"])
    assert item.public_title == "碎碎念一则 (26.4.26.)"
    assert _beijing(item.first_published_at) == datetime(2026, 4, 26, 10, 0, tzinfo=BEIJING_TZ)


def test_public_to_archive_or_draft_uses_clear_backend_suffix_and_restores_public_identity(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    create_response = client.post(
        f"{ADMIN_BASE}/",
        json=_thought_payload("public-title-restore", "碎碎念一则 (26.4.26.)-草稿"),
        headers=admin_headers,
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    publish_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={
            "status": "published",
            "visibility": "public",
            "published_at": "2026-04-26T11:00:00+08:00",
        },
        headers=admin_headers,
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["title"] == "碎碎念一则 (26.4.26.)"

    monkeypatch.setattr(
        content_service,
        "shanghai_now",
        lambda: datetime(2026, 4, 27, 8, 0, tzinfo=BEIJING_TZ),
    )
    archive_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={"visibility": "private"},
        headers=admin_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"
    assert archive_response.json()["title"] == "碎碎念一则 (26.4.26.)-公开转归档"
    archived_item = _get_thought("public-title-restore")
    assert _beijing(archived_item.published_at) == datetime(2026, 4, 27, 8, 0, tzinfo=BEIJING_TZ)
    assert _beijing(archived_item.first_archived_at) == datetime(2026, 4, 27, 8, 0, tzinfo=BEIJING_TZ)

    draft_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={"visibility": "public"},
        headers=admin_headers,
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["status"] == "draft"
    assert draft_response.json()["title"] == "碎碎念一则 (26.4.26.)-公开转草稿"

    restore_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={"status": "published", "visibility": "public"},
        headers=admin_headers,
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["title"] == "碎碎念一则 (26.4.26.)"
    item = _get_thought("public-title-restore")
    assert _beijing(item.published_at) == datetime(2026, 4, 26, 11, 0, tzinfo=BEIJING_TZ)
    assert _beijing(item.first_published_at) == datetime(2026, 4, 26, 11, 0, tzinfo=BEIJING_TZ)
    assert _beijing(item.first_archived_at) == datetime(2026, 4, 27, 8, 0, tzinfo=BEIJING_TZ)


def test_public_title_and_time_survive_normal_edits_but_manual_time_is_respected(
    client,
    admin_headers,
) -> None:
    create_response = client.post(
        f"{ADMIN_BASE}/",
        json=_thought_payload("public-title-stable-edit", "碎碎念一则 (26.4.26.)-草稿"),
        headers=admin_headers,
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    publish_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={
            "status": "published",
            "visibility": "public",
            "published_at": "2026-04-26T12:00:00+08:00",
        },
        headers=admin_headers,
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["title"] == "碎碎念一则 (26.4.26.)"

    edit_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={"body": "edited body only"},
        headers=admin_headers,
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["title"] == "碎碎念一则 (26.4.26.)"
    item = _get_thought("public-title-stable-edit")
    assert _beijing(item.published_at) == datetime(2026, 4, 26, 12, 0, tzinfo=BEIJING_TZ)

    manual_time_response = client.put(
        f"{ADMIN_BASE}/{item_id}",
        json={"published_at": "2026-04-25T08:00:00+08:00"},
        headers=admin_headers,
    )
    assert manual_time_response.status_code == 200
    assert manual_time_response.json()["title"] == "碎碎念一则 (26.4.26.)"
    item = _get_thought("public-title-stable-edit")
    assert _beijing(item.published_at) == datetime(2026, 4, 25, 8, 0, tzinfo=BEIJING_TZ)
    assert item.public_title == "碎碎念一则 (26.4.26.)"

from __future__ import annotations

from typing import Any

ADMIN_BASE = "/api/v1/admin"
SITE_BASE = "/api/v1/site"


def _create_public_post(
    client: Any,
    admin_headers: dict[str, str],
    *,
    slug: str,
    kind: str,
) -> None:
    response = client.post(
        f"{ADMIN_BASE}/posts/",
        headers=admin_headers,
        json={
            "slug": slug,
            "title": slug,
            "body": "公开内容",
            "visibility": "public",
            "kind": kind,
        },
    )
    assert response.status_code == 201


def test_public_manuscript_and_note_endpoints_do_not_mix_content(client, admin_headers) -> None:
    manuscript_slug = "public-manuscript-only"
    note_slug = "public-note-only"
    _create_public_post(client, admin_headers, slug=manuscript_slug, kind="manuscript")
    _create_public_post(client, admin_headers, slug=note_slug, kind="note")

    manuscripts = client.get(f"{SITE_BASE}/posts")
    notes = client.get(f"{SITE_BASE}/notes")

    assert manuscripts.status_code == 200
    assert notes.status_code == 200
    manuscript_items = {item["slug"]: item for item in manuscripts.json()["items"]}
    note_items = {item["slug"]: item for item in notes.json()["items"]}
    assert manuscript_items[manuscript_slug]["kind"] == "manuscript"
    assert note_slug not in manuscript_items
    assert note_items[note_slug]["kind"] == "note"
    assert manuscript_slug not in note_items

    assert client.get(f"{SITE_BASE}/posts/{manuscript_slug}").status_code == 200
    assert client.get(f"{SITE_BASE}/notes/{note_slug}").status_code == 200
    assert client.get(f"{SITE_BASE}/posts/{note_slug}").status_code == 404
    assert client.get(f"{SITE_BASE}/notes/{manuscript_slug}").status_code == 404

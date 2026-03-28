from __future__ import annotations


def test_read_resume_returns_seeded_resume_bundle(client) -> None:
    response = client.get("/api/v1/site/resume")

    assert response.status_code == 200

    payload = response.json()
    assert payload["title"] == "Felix"
    assert payload["summary"]
    assert payload["location"] == "上海 / Remote"
    assert payload["email"] == "felix@example.com"
    assert payload["profile_image_url"]

    assert "subtitle" not in payload
    assert "download_label" not in payload
    assert "template_key" not in payload
    assert "accent_tone" not in payload
    assert "availability" not in payload
    assert "website" not in payload
    assert "highlights" not in payload
    assert "skill_groups" not in payload
    assert "experiences" not in payload

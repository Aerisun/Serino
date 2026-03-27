from __future__ import annotations


def test_read_diary_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/site/diary")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 7
    assert payload["items"][0]["slug"] == "spring-equinox-and-warm-light"


def test_read_diary_detail_returns_seeded_entry(client) -> None:
    response = client.get("/api/v1/site/diary/spring-equinox-and-warm-light")

    assert response.status_code == 200

    payload = response.json()
    assert payload["slug"] == "spring-equinox-and-warm-light"
    assert payload["title"] == "春分，天气转暖"


def test_read_diary_detail_returns_404_for_unknown_slug(client) -> None:
    response = client.get("/api/v1/site/diary/missing-entry")

    assert response.status_code == 404

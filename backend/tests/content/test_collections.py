from __future__ import annotations


def test_read_thoughts_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/public/thoughts")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 8
    assert payload["items"][0]["slug"] == "spacing-rhythm-note"


def test_read_excerpts_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/public/excerpts")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 7
    assert payload["items"][0]["slug"] == "harmony-in-blank-space"

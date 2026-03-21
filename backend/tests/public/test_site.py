from __future__ import annotations


def test_read_site_returns_seeded_payload(client) -> None:
    response = client.get("/api/v1/public/site")

    assert response.status_code == 200

    payload = response.json()
    assert payload["site"]["name"] == "Felix"
    assert payload["site"]["title"] == "Aerisun"
    assert len(payload["social_links"]) >= 1
    assert len(payload["poems"]) == 12

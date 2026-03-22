from __future__ import annotations


def test_search_returns_results(client):
    r = client.get("/api/v1/public/search", params={"q": "test"})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_search_requires_query(client):
    r = client.get("/api/v1/public/search")
    assert r.status_code == 422


def test_search_empty_results(client):
    r = client.get("/api/v1/public/search", params={"q": "nonexistent_xyz_query_12345"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0

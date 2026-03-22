from __future__ import annotations


def test_sitemap_xml(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    assert '<?xml version="1.0"' in r.text
    assert "<urlset" in r.text
    assert "<loc>" in r.text


def test_robots_txt(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "User-agent: *" in r.text
    assert "Sitemap:" in r.text

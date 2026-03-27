from __future__ import annotations


def test_request_id_header(client):
    """验证每个请求都返回 X-Request-ID 头。"""
    resp = client.get("/api/v1/site/healthz")
    assert resp.status_code == 200
    request_id = resp.headers.get("x-request-id")
    assert request_id is not None
    assert len(request_id) > 10  # UUID 格式


def test_request_id_unique(client):
    """验证不同请求的 ID 不同。"""
    resp1 = client.get("/api/v1/site/healthz")
    resp2 = client.get("/api/v1/site/healthz")
    id1 = resp1.headers.get("x-request-id")
    id2 = resp2.headers.get("x-request-id")
    assert id1 != id2

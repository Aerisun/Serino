"""Tests for the public page-view beacon endpoint."""

from __future__ import annotations

from datetime import timedelta

from aerisun.core.db import get_session_factory
from aerisun.core.time import shanghai_now
from aerisun.domain.content.models import PostEntry
from aerisun.domain.ops import service as ops_service
from aerisun.domain.ops.service import VisitRecordPayload, persist_visit_record_payload
from aerisun.domain.waline.service import set_counter_value

ENDPOINT = "/api/v1/site-interactions/visit"


def test_visit_beacon_accepts_payload(client):
    resp = client.post(
        ENDPOINT,
        json={
            "url": "/posts/123?utm_source=twitter",
            "referer": "https://www.google.com/",
            "screen": "1920x1080",
            "language": "zh-CN",
            "load_ms": 842,
        },
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_visit_beacon_accepts_oversized_load_ms(client):
    # An absurd load time must not reject the beacon; it is clamped server-side.
    resp = client.post(
        ENDPOINT,
        json={"url": "/", "load_ms": 10_000_000},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_content_visit_beacon_is_visible_on_immediate_public_refresh(client):
    path = "/posts/why-i-choose-indie-design"
    set_counter_value(url=path, pageview_count=0)

    session_factory = get_session_factory()
    with session_factory() as session:
        post = session.query(PostEntry).filter(PostEntry.slug == "why-i-choose-indie-design").first()
        assert post is not None
        post.view_count = 0
        session.commit()

    resp = client.post(
        ENDPOINT,
        json={"url": path, "load_ms": 120},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"},
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True

    detail = client.get("/api/v1/site/posts/why-i-choose-indie-design").json()
    assert detail["view_count"] == 1


def test_content_visit_updates_persisted_view_count_before_async_queue(monkeypatch, client):
    path = "/posts/why-i-choose-indie-design"
    set_counter_value(url=path, pageview_count=0)
    with get_session_factory()() as session:
        post = session.query(PostEntry).filter(PostEntry.slug == "why-i-choose-indie-design").one()
        post.view_count = 0
        session.commit()
    enqueued_payloads: list[VisitRecordPayload] = []

    def fake_enqueue(payload: VisitRecordPayload) -> bool:
        enqueued_payloads.append(payload)
        return True

    monkeypatch.setattr(ops_service, "enqueue_visit_record", fake_enqueue)

    accepted = ops_service.record_page_visit(
        url=path,
        referer=None,
        ip_address="203.0.113.44",
        user_agent="Mozilla/5.0",
        load_ms=120,
    )

    assert accepted is True
    assert len(enqueued_payloads) == 1
    with get_session_factory()() as session:
        post = session.query(PostEntry).filter(PostEntry.slug == "why-i-choose-indie-design").one()
        assert post.view_count == 1
    assert enqueued_payloads[0].increment_public_counter is False

    session_factory = get_session_factory()
    with session_factory() as session:
        persist_visit_record_payload(session, enqueued_payloads[0])
    with session_factory() as session:
        post = session.query(PostEntry).filter(PostEntry.slug == "why-i-choose-indie-design").one()
        assert post.view_count == 1


def test_visit_beacon_ignores_static_and_ai_entry_paths(monkeypatch):
    enqueued_payloads: list[VisitRecordPayload] = []

    def fake_enqueue(payload: VisitRecordPayload) -> bool:
        enqueued_payloads.append(payload)
        return True

    monkeypatch.setattr(ops_service, "enqueue_visit_record", fake_enqueue)

    for path in ("/manifest.webmanifest", "/llms.txt", "/resume.md", "/feeds/posts.xml", "/assets/app.js"):
        accepted = ops_service.record_page_visit(
            url=path,
            referer=None,
            ip_address="203.0.113.44",
            user_agent="Mozilla/5.0",
            load_ms=120,
        )
        assert accepted is False

    assert enqueued_payloads == []


def test_visit_beacon_requires_url(client):
    resp = client.post(ENDPOINT, json={"referer": "https://example.com/"})
    assert resp.status_code == 422


def test_persisted_content_visit_increments_article_historical_view_count(client):
    path = "/posts/why-i-choose-indie-design"
    set_counter_value(url=path, pageview_count=0)

    session_factory = get_session_factory()
    with session_factory() as session:
        post = session.query(PostEntry).filter(PostEntry.slug == "why-i-choose-indie-design").first()
        assert post is not None
        post.view_count = 41
        persist_visit_record_payload(
            session,
            VisitRecordPayload(
                visited_at=shanghai_now(),
                path=path,
                ip_address="203.0.113.44",
                user_agent="Mozilla/5.0",
                referer=None,
                status_code=200,
                duration_ms=120,
                is_bot=False,
            ),
        )
        assert post.view_count == 42

    detail = client.get("/api/v1/site/posts/why-i-choose-indie-design").json()
    listing = client.get("/api/v1/site/posts").json()["items"]
    listed_post = next(item for item in listing if item["slug"] == "why-i-choose-indie-design")

    assert detail["view_count"] == 42
    assert listed_post["view_count"] == 42


def test_persisted_content_visit_does_not_change_article_updated_at(client):
    path = "/posts/why-i-choose-indie-design"
    session_factory = get_session_factory()

    with session_factory() as session:
        post = session.query(PostEntry).filter(PostEntry.slug == "why-i-choose-indie-design").one()
        post.view_count = 0
        post.updated_at = shanghai_now() - timedelta(days=1)
        session.commit()
        edited_at = post.updated_at

        persist_visit_record_payload(
            session,
            VisitRecordPayload(
                visited_at=shanghai_now(),
                path=path,
                ip_address="203.0.113.44",
                user_agent="Mozilla/5.0",
                referer=None,
                status_code=200,
                duration_ms=120,
                is_bot=False,
            ),
        )
        session.refresh(post)

        assert post.view_count == 1
        assert post.updated_at.replace(tzinfo=None) == edited_at.replace(tzinfo=None)

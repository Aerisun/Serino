from __future__ import annotations

from datetime import datetime, timedelta

from aerisun.core.db import get_session_factory
from aerisun.core.time import BEIJING_TZ, shanghai_now
from aerisun.domain.content.models import PostEntry
from aerisun.domain.diary_access.models import DiaryAccessRequest
from aerisun.domain.site_auth.models import SiteUser


def _login_site_user(client, *, email: str = "search-reader@example.com", display_name: str = "Search Reader") -> None:
    response = client.post(
        "/api/v1/site-auth/email",
        json={
            "email": email,
            "display_name": display_name,
            "avatar_url": f"/api/v1/avatars/10.x/notionists/svg?seed={display_name}",
        },
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_search_returns_results(client):
    r = client.get("/api/v1/site/search", params={"q": "test"})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_search_requires_query(client):
    r = client.get("/api/v1/site/search")
    assert r.status_code == 422


def test_search_empty_results(client):
    r = client.get("/api/v1/site/search", params={"q": "nonexistent_xyz_query_12345"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0


def test_search_splits_keywords_and_highlights_terms_in_first_keyword_snippet(client):
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            PostEntry(
                slug="multi-keyword-search",
                title="多关键词检索",
                summary="一段用于搜索的摘要",
                body=(
                    "页面开头先提到红色按钮，但这里不是要展示的文段。"
                    "后面才写到晚霞慢慢铺开，红色云层落在玻璃窗上。"
                    "这段文字用来确认搜索片段围绕第一个关键词生成。"
                ),
                visibility="public",
                published_at=datetime(2026, 6, 30, 20, 0, tzinfo=BEIJING_TZ),
            )
        )
        session.commit()

    response = client.get("/api/v1/site/search", params={"q": "晚霞 红色"})

    assert response.status_code == 200
    data = response.json()
    item = next(item for item in data["items"] if item["slug"] == "multi-keyword-search")
    assert "<mark>晚霞</mark>" in item["snippet"]
    assert "<mark>红色</mark>" in item["snippet"]
    assert "后面才写到" in item["snippet"]


def test_search_excludes_diary_body_matches_for_logged_in_user_without_diary_access(client):
    _login_site_user(client, email="search-no-access@example.com", display_name="No Access")

    response = client.get("/api/v1/site/search", params={"q": "花苞"})

    assert response.status_code == 200
    assert all(item["type"] != "diary" for item in response.json()["items"])


def test_search_includes_diary_body_matches_for_user_with_diary_access(client):
    _login_site_user(client)

    session_factory = get_session_factory()
    with session_factory() as session:
        user = session.query(SiteUser).filter(SiteUser.email == "search-reader@example.com").one()
        session.add(
            DiaryAccessRequest(
                site_user_id=user.id,
                reason="Search should include accessible diary content.",
                status="approved",
                granted_at=shanghai_now(),
                expires_at=shanghai_now() + timedelta(days=7),
            )
        )
        session.commit()

    response = client.get("/api/v1/site/search", params={"q": "花苞"})

    assert response.status_code == 200
    diary_item = next(item for item in response.json()["items"] if item["slug"] == "spring-equinox-and-warm-light")
    assert diary_item["type"] == "diary"
    assert "<mark>花苞</mark>" in diary_item["snippet"]

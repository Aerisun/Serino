from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.subscription.models import ContentSubscriber
from aerisun.domain.subscription.service import get_subscription_config_orm

PUBLIC_BASE = "/api/v1/site"


def _enable_subscriptions() -> None:
    with get_session_factory()() as session:
        config = get_subscription_config_orm(session)
        config.enabled = True
        session.commit()


def test_site_config_exposes_public_subscription_flag(client) -> None:
    response = client.get(f"{PUBLIC_BASE}/site")

    assert response.status_code == 200
    assert response.json()["site"]["feature_flags"]["content_subscription"] is False

    _enable_subscriptions()

    enabled_response = client.get(f"{PUBLIC_BASE}/site")

    assert enabled_response.status_code == 200
    assert enabled_response.json()["site"]["feature_flags"]["content_subscription"] is True


def test_public_subscription_requires_enabled(client) -> None:
    response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "订阅功能尚未开启"


def test_public_subscription_creates_and_updates_subscriber(client) -> None:
    _enable_subscriptions()

    create_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )

    assert create_response.status_code == 201
    assert create_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts", "thoughts"],
        "subscribed": True,
    }

    update_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "Reader@Example.com", "content_types": ["diary", "excerpts"]},
    )

    assert update_response.status_code == 201
    assert update_response.json() == {
        "email": "reader@example.com",
        "content_types": ["diary", "excerpts"],
        "subscribed": True,
    }

    with get_session_factory()() as session:
        subscribers = session.query(ContentSubscriber).all()

    assert len(subscribers) == 1
    assert subscribers[0].email == "reader@example.com"
    assert subscribers[0].content_types == ["diary", "excerpts"]

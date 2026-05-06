from __future__ import annotations

import bcrypt
import pytest

LIST_CASES = [
    ("posts", "/api/v1/site/posts"),
    ("diary", "/api/v1/site/diary"),
    ("thoughts", "/api/v1/site/thoughts"),
    ("excerpts", "/api/v1/site/excerpts"),
]

DETAIL_CASES = [
    ("posts", "/api/v1/site/posts/{slug}"),
    ("diary", "/api/v1/site/diary/{slug}"),
]

ADMIN_EMAIL = "private-owner@example.com"
ADMIN_PASSWORD = "route-password"


def _seed_bound_admin_email(*, email: str = ADMIN_EMAIL, admin_password: str = ADMIN_PASSWORD) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.admin_binding import bind_site_admin_identity_by_email
    from aerisun.domain.site_auth.config_service import get_site_auth_config_orm
    from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest

    factory = get_session_factory()
    with factory() as session:
        admin_user = session.query(AdminUser).filter(AdminUser.username == "archive-visibility-admin").first()
        if admin_user is None:
            admin_user = AdminUser(
                username="archive-visibility-admin",
                password_hash=bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode(),
            )
            session.add(admin_user)
            session.flush()

        config = get_site_auth_config_orm(session)
        config.admin_email_enabled = True
        session.commit()

        bind_site_admin_identity_by_email(
            session,
            SiteAdminEmailIdentityBindRequest(email=email),
            admin_user_id=admin_user.id,
        )


def _login_as_site_admin(client, *, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> None:
    response = client.post(
        "/api/v1/site-auth/email",
        json={
            "email": email,
            "display_name": "Archive Owner",
            "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=archive-owner",
            "admin_password": password,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["is_admin"] is True


def _create_private_item(client, admin_headers: dict[str, str], *, content_type: str, slug: str) -> dict:
    payload: dict[str, object] = {
        "slug": slug,
        "title": f"Private {content_type} title",
        "body": f"Private {content_type} body for owner visibility checks.",
        "summary": f"Private {content_type} summary",
        "tags": ["private"],
        "visibility": "private",
        "published_at": "2026-04-03T12:00:00+00:00",
    }
    if content_type == "excerpts":
        payload["author_name"] = "Archive Curator"
        payload["source"] = "Archive Source"

    response = client.post(
        f"/api/v1/admin/{content_type}/",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 201
    created = response.json()
    assert "status" not in created
    assert created["visibility"] == "private"
    return created


@pytest.mark.parametrize(("content_type", "list_path"), LIST_CASES)
def test_public_content_lists_hide_private_items(client, admin_headers, content_type: str, list_path: str) -> None:
    slug = f"private-{content_type}-hidden"
    _create_private_item(client, admin_headers, content_type=content_type, slug=slug)

    response = client.get(list_path)

    assert response.status_code == 200
    assert all(item["slug"] != slug for item in response.json()["items"])


@pytest.mark.parametrize(("content_type", "list_path"), LIST_CASES)
def test_admin_elevated_site_user_can_see_private_items_in_lists(
    client,
    admin_headers,
    content_type: str,
    list_path: str,
) -> None:
    slug = f"private-{content_type}-visible"
    _create_private_item(client, admin_headers, content_type=content_type, slug=slug)
    _seed_bound_admin_email()
    _login_as_site_admin(client)

    response = client.get(list_path)

    assert response.status_code == 200
    private_item = next(item for item in response.json()["items"] if item["slug"] == slug)
    assert "status" not in private_item
    assert private_item["visibility"] == "private"


@pytest.mark.parametrize(("content_type", "detail_path"), DETAIL_CASES)
def test_public_content_details_hide_private_items(client, admin_headers, content_type: str, detail_path: str) -> None:
    slug = f"private-{content_type}-detail-hidden"
    _create_private_item(client, admin_headers, content_type=content_type, slug=slug)

    response = client.get(detail_path.format(slug=slug))

    assert response.status_code == 404


@pytest.mark.parametrize(("content_type", "detail_path"), DETAIL_CASES)
def test_admin_elevated_site_user_can_open_private_details(
    client,
    admin_headers,
    content_type: str,
    detail_path: str,
) -> None:
    slug = f"private-{content_type}-detail-visible"
    _create_private_item(client, admin_headers, content_type=content_type, slug=slug)
    _seed_bound_admin_email()
    _login_as_site_admin(client)

    response = client.get(detail_path.format(slug=slug))

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == slug
    assert "status" not in payload
    assert payload["visibility"] == "private"

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import bcrypt
import httpx
import respx


def _seed_bound_admin_email(
    *,
    email: str,
    shared_password: str = "shared-admin-password",
    console_methods: list[str] | None = None,
) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.admin_binding import bind_site_admin_identity_by_email
    from aerisun.domain.site_auth.config_service import get_site_auth_config_orm
    from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest

    factory = get_session_factory()
    with factory() as session:
        admin_user = session.query(AdminUser).filter(AdminUser.username == "site-auth-admin").first()
        if admin_user is None:
            admin_user = AdminUser(
                username="site-auth-admin",
                password_hash=bcrypt.hashpw(b"route-password", bcrypt.gensalt()).decode(),
            )
            session.add(admin_user)
            session.flush()

        config = get_site_auth_config_orm(session)
        config.admin_email_enabled = True
        config.admin_console_auth_methods = list(console_methods or [])
        config.admin_email_password_hash = bcrypt.hashpw(
            shared_password.encode(),
            bcrypt.gensalt(),
        ).decode()
        session.commit()

        bind_site_admin_identity_by_email(
            session,
            SiteAdminEmailIdentityBindRequest(email=email),
            admin_user_id=admin_user.id,
        )


def _seed_bound_google_admin(
    *,
    email: str,
    provider_subject: str,
    console_methods: list[str] | None = None,
) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.core.time import shanghai_now
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.admin_binding import upsert_admin_identity
    from aerisun.domain.site_auth.config_service import get_site_auth_config_orm
    from aerisun.domain.site_auth.models import SiteUser, SiteUserOAuthAccount

    factory = get_session_factory()
    with factory() as session:
        admin_user = session.query(AdminUser).filter(AdminUser.username == "oauth-site-admin").first()
        if admin_user is None:
            admin_user = AdminUser(
                username="oauth-site-admin",
                password_hash=bcrypt.hashpw(b"route-password", bcrypt.gensalt()).decode(),
            )
            session.add(admin_user)
            session.flush()

        config = get_site_auth_config_orm(session)
        config.admin_auth_methods = ["google"]
        config.admin_console_auth_methods = list(console_methods or [])
        config.google_client_id = "google-client-id"
        config.google_client_secret = "google-client-secret"

        user = session.query(SiteUser).filter(SiteUser.email == email).first()
        if user is None:
            user = SiteUser(
                email=email,
                display_name="Google Admin",
                avatar_url="https://example.com/google-admin.png",
                primary_auth_provider="google",
                last_login_at=shanghai_now(),
            )
            session.add(user)
            session.flush()

        oauth_account = (
            session.query(SiteUserOAuthAccount)
            .filter(
                SiteUserOAuthAccount.provider == "google",
                SiteUserOAuthAccount.provider_subject == provider_subject,
            )
            .first()
        )
        if oauth_account is None:
            session.add(
                SiteUserOAuthAccount(
                    site_user_id=user.id,
                    provider="google",
                    provider_subject=provider_subject,
                    provider_email=email,
                    provider_display_name="Google Admin",
                    provider_avatar_url="https://example.com/google-admin.png",
                )
            )
            session.flush()

        session.commit()

        upsert_admin_identity(
            session,
            site_user=user,
            admin_user_id=admin_user.id,
            provider="google",
            identifier=provider_subject,
            email=email,
            provider_display_name="Google Admin",
        )


def _login_site_user(
    client,
    *,
    email: str,
    display_name: str = "Visitor",
    avatar_seed: str = "visitor",
    admin_password: str | None = None,
):
    payload = {
        "email": email,
        "display_name": display_name,
        "avatar_url": f"https://api.dicebear.com/9.x/notionists/svg?seed={avatar_seed}",
    }
    if admin_password is not None:
        payload["admin_password"] = admin_password
    return client.post("/api/v1/site-auth/email", json=payload)


def test_bound_admin_email_requires_shared_password_before_site_login(client) -> None:
    email = "bound-admin@example.com"
    _seed_bound_admin_email(email=email)

    prompt_response = _login_site_user(client, email=email)
    assert prompt_response.status_code == 200
    prompt_payload = prompt_response.json()
    assert prompt_payload["authenticated"] is False
    assert prompt_payload["requires_admin_password"] is True

    me_response = client.get("/api/v1/site-auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["authenticated"] is False

    wrong_password_response = _login_site_user(
        client,
        email=email,
        admin_password="wrong-password",
    )
    assert wrong_password_response.status_code == 401
    assert wrong_password_response.json()["detail"] == "管理员邮箱密码错误。"

    success_response = _login_site_user(
        client,
        email=email,
        admin_password="shared-admin-password",
    )
    assert success_response.status_code == 200
    success_payload = success_response.json()
    assert success_payload["authenticated"] is True
    assert success_payload["requires_admin_password"] is False
    assert success_payload["user"]["is_admin"] is True
    assert success_payload["user"]["can_access_admin_console"] is False

    me_after = client.get("/api/v1/site-auth/me")
    assert me_after.status_code == 200
    me_payload = me_after.json()
    assert me_payload["authenticated"] is True
    assert me_payload["user"]["is_admin"] is True
    assert me_payload["user"]["can_access_admin_console"] is False


def test_exchange_site_user_requires_admin_elevated_session(client) -> None:
    normal_login = _login_site_user(
        client,
        email="plain-visitor@example.com",
        display_name="Plain Visitor",
        avatar_seed="plain-visitor",
    )
    assert normal_login.status_code == 200
    assert normal_login.json()["authenticated"] is True

    denied = client.post("/api/v1/admin/auth/exchange-site-user")
    assert denied.status_code == 401
    assert denied.json()["detail"] == "当前站点会话还没有完成管理员验证。"

    client.post("/api/v1/site-auth/logout")

    email = "exchange-admin@example.com"
    _seed_bound_admin_email(email=email)
    elevated_login = _login_site_user(
        client,
        email=email,
        admin_password="shared-admin-password",
    )
    assert elevated_login.status_code == 200
    assert elevated_login.json()["user"]["is_admin"] is True
    assert elevated_login.json()["user"]["can_access_admin_console"] is False

    denied_console = client.post("/api/v1/admin/auth/exchange-site-user")
    assert denied_console.status_code == 401
    assert denied_console.json()["detail"] == "当前管理员身份未开启进入管理台。"

    client.post("/api/v1/site-auth/logout")

    _seed_bound_admin_email(email=email, console_methods=["email"])
    elevated_login = _login_site_user(
        client,
        email=email,
        admin_password="shared-admin-password",
    )
    assert elevated_login.status_code == 200
    assert elevated_login.json()["user"]["is_admin"] is True
    assert elevated_login.json()["user"]["can_access_admin_console"] is True

    exchanged = client.post("/api/v1/admin/auth/exchange-site-user")
    assert exchanged.status_code == 200
    assert exchanged.json()["token"]


@respx.mock
def test_google_admin_binding_elevates_site_session_after_oauth_login(client) -> None:
    email = "google-admin@example.com"
    provider_subject = "google-sub-123"
    _seed_bound_google_admin(
        email=email,
        provider_subject=provider_subject,
        console_methods=["google"],
    )

    start_response = client.get(
        "/api/v1/site-auth/oauth/google/start",
        params={"return_to": "/"},
    )
    assert start_response.status_code == 200
    auth_url = start_response.json()["authorization_url"]
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "oauth-access-token"})
    )
    respx.get("https://openidconnect.googleapis.com/v1/userinfo").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": email,
                "name": "Google Admin",
                "picture": "https://example.com/google-admin.png",
                "sub": provider_subject,
            },
        )
    )

    callback_response = client.get(
        "/api/v1/site-auth/oauth/google/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )
    assert callback_response.status_code == 302

    me_response = client.get("/api/v1/site-auth/me")
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["authenticated"] is True
    assert me_payload["user"]["is_admin"] is True
    assert me_payload["user"]["can_access_admin_console"] is True

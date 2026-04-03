from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt


def _create_admin_user(
    *,
    username: str,
    password: str,
    password_change_required: bool = False,
):
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser

    factory = get_session_factory()
    with factory() as session:
        user = session.query(AdminUser).filter(AdminUser.username == username).first()
        if user is None:
            user = AdminUser(
                username=username,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                password_change_required=password_change_required,
            )
            session.add(user)
        else:
            user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user.password_change_required = password_change_required
        session.commit()
        session.refresh(user)
        return user.id


def _create_admin_session(*, admin_user_id: str, token: str) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminSession

    factory = get_session_factory()
    with factory() as session:
        existing = session.query(AdminSession).filter(AdminSession.session_token == token).first()
        if existing is None:
            session.add(
                AdminSession(
                    admin_user_id=admin_user_id,
                    session_token=token,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )
        else:
            existing.admin_user_id = admin_user_id
            existing.expires_at = datetime.now(UTC) + timedelta(hours=24)
        session.commit()


def test_admin_dashboard_requires_authentication(client) -> None:
    response = client.get("/api/v1/admin/system/dashboard/stats")

    assert response.status_code == 401


def test_admin_login_rejects_unknown_user(client) -> None:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "felix", "password": "not-the-right-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_bound_admin_email_login_requires_shared_password(client) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.admin_binding import bind_site_admin_identity_by_email
    from aerisun.domain.site_auth.config_service import get_site_auth_config_orm
    from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest

    factory = get_session_factory()
    with factory() as session:
        admin_user = session.query(AdminUser).filter(AdminUser.username == "bound-admin").first()
        if admin_user is None:
            admin_user = AdminUser(
                username="bound-admin",
                password_hash=bcrypt.hashpw(b"bound-admin-password", bcrypt.gensalt()).decode(),
            )
            session.add(admin_user)
            session.flush()

        config = get_site_auth_config_orm(session)
        config.admin_email_enabled = True
        config.admin_console_auth_methods = ["email"]
        config.admin_email_password_hash = bcrypt.hashpw(
            b"shared-admin-password",
            bcrypt.gensalt(),
        ).decode()
        session.commit()

        bind_site_admin_identity_by_email(
            session,
            SiteAdminEmailIdentityBindRequest(email="bound-admin@example.com"),
            admin_user_id=admin_user.id,
        )

    wrong_password = client.post(
        "/api/v1/admin/auth/email",
        json={"email": "bound-admin@example.com", "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["detail"] == "管理员邮箱密码错误。"

    success = client.post(
        "/api/v1/admin/auth/email",
        json={
            "email": "bound-admin@example.com",
            "password": "shared-admin-password",
        },
    )
    assert success.status_code == 200
    assert success.json()["token"]


def test_password_change_required_admin_is_limited_to_self_service_endpoints(client) -> None:
    _create_admin_user(
        username="forced-admin",
        password="temp-admin-password",
        password_change_required=True,
    )

    login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "forced-admin", "password": "temp-admin-password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    me = client.get("/api/v1/admin/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["password_change_required"] is True

    sessions = client.get("/api/v1/admin/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1

    blocked_dashboard = client.get("/api/v1/admin/system/dashboard/stats", headers=headers)
    assert blocked_dashboard.status_code == 403
    assert blocked_dashboard.json()["detail"] == "Password change required before accessing admin console"

    blocked_profile = client.put("/api/v1/admin/auth/profile", headers=headers, json={"username": "renamed-admin"})
    assert blocked_profile.status_code == 403
    assert blocked_profile.json()["detail"] == "Password change required before accessing admin console"


def test_password_change_required_password_reset_unlocks_current_session_and_revokes_others(client) -> None:
    admin_user_id = _create_admin_user(
        username="rotation-admin",
        password="temp-admin-password",
        password_change_required=True,
    )
    _create_admin_session(admin_user_id=admin_user_id, token="rotation-secondary-token")

    login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "rotation-admin", "password": "temp-admin-password"},
    )
    assert login.status_code == 200
    current_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    secondary_headers = {"Authorization": "Bearer rotation-secondary-token"}

    change_password = client.put(
        "/api/v1/admin/auth/password",
        headers=current_headers,
        json={
            "current_password": "temp-admin-password",
            "new_password": "new-admin-password",
        },
    )
    assert change_password.status_code == 204

    me = client.get("/api/v1/admin/auth/me", headers=current_headers)
    assert me.status_code == 200
    assert me.json()["password_change_required"] is False

    dashboard = client.get("/api/v1/admin/system/dashboard/stats", headers=current_headers)
    assert dashboard.status_code == 200

    revoked = client.get("/api/v1/admin/auth/me", headers=secondary_headers)
    assert revoked.status_code == 401

    old_login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "rotation-admin", "password": "temp-admin-password"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "rotation-admin", "password": "new-admin-password"},
    )
    assert new_login.status_code == 200


def test_password_change_required_bound_admin_email_login_is_still_console_locked(client) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.admin_binding import bind_site_admin_identity_by_email
    from aerisun.domain.site_auth.config_service import get_site_auth_config_orm
    from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest

    factory = get_session_factory()
    with factory() as session:
        admin_user = session.query(AdminUser).filter(AdminUser.username == "bound-locked-admin").first()
        if admin_user is None:
            admin_user = AdminUser(
                username="bound-locked-admin",
                password_hash=bcrypt.hashpw(b"bound-admin-password", bcrypt.gensalt()).decode(),
                password_change_required=True,
            )
            session.add(admin_user)
            session.flush()
        else:
            admin_user.password_change_required = True

        config = get_site_auth_config_orm(session)
        config.admin_email_enabled = True
        config.admin_console_auth_methods = ["email"]
        config.admin_email_password_hash = bcrypt.hashpw(
            b"shared-admin-password",
            bcrypt.gensalt(),
        ).decode()
        session.commit()

        bind_site_admin_identity_by_email(
            session,
            SiteAdminEmailIdentityBindRequest(email="bound-locked-admin@example.com"),
            admin_user_id=admin_user.id,
        )

    success = client.post(
        "/api/v1/admin/auth/email",
        json={
            "email": "bound-locked-admin@example.com",
            "password": "shared-admin-password",
        },
    )
    assert success.status_code == 200
    headers = {"Authorization": f"Bearer {success.json()['token']}"}

    me = client.get("/api/v1/admin/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["password_change_required"] is True

    blocked_dashboard = client.get("/api/v1/admin/system/dashboard/stats", headers=headers)
    assert blocked_dashboard.status_code == 403
    assert blocked_dashboard.json()["detail"] == "Password change required before accessing admin console"

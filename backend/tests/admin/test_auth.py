from __future__ import annotations

import bcrypt


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

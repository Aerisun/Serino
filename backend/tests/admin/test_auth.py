from __future__ import annotations


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

from __future__ import annotations

import pytest


def _create_visitor_with_oauth_and_session(session):
    from datetime import timedelta

    from aerisun.core.time import shanghai_now
    from aerisun.domain.site_auth.models import SiteUser, SiteUserOAuthAccount, SiteUserSession

    visitor = SiteUser(
        email="visitor-delete@example.com",
        display_name="Visitor to delete",
        avatar_url="https://example.com/visitor.png",
        primary_auth_provider="google",
        last_login_at=shanghai_now(),
    )
    session.add(visitor)
    session.flush()
    session.add_all(
        [
            SiteUserOAuthAccount(
                site_user_id=visitor.id,
                provider="google",
                provider_subject="visitor-delete-subject",
                provider_email=visitor.email,
                provider_display_name=visitor.display_name,
            ),
            SiteUserSession(
                site_user_id=visitor.id,
                session_token="visitor-delete-session-token",
                expires_at=shanghai_now() + timedelta(days=1),
            ),
        ]
    )
    session.commit()
    return visitor


def test_admin_deletes_visitor_and_all_linked_waline_record_trees(client, admin_headers) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.site_auth.models import SiteUser, SiteUserOAuthAccount, SiteUserSession
    from aerisun.domain.waline.service import create_waline_record, get_waline_record_by_id

    factory = get_session_factory()
    with factory() as session:
        visitor = _create_visitor_with_oauth_and_session(session)
        visitor_id = visitor.id

    comment = create_waline_record(
        comment="visitor comment",
        nick="Visitor to delete",
        mail="visitor-delete@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        site_user_id=visitor_id,
        avatar_key=f"site-user-{visitor_id}",
    )
    comment_reply = create_waline_record(
        comment="another visitor replied",
        nick="Another visitor",
        mail="another@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        parent_id=comment.id,
        site_user_id="another-visitor",
    )
    guestbook = create_waline_record(
        comment="visitor guestbook entry",
        nick="Visitor to delete",
        mail="visitor-delete@example.com",
        link=None,
        status="approved",
        url="/guestbook",
        site_user_id=visitor_id,
        avatar_key=f"site-user-{visitor_id}",
    )

    response = client.delete(
        f"/api/v1/admin/visitors/users/{visitor_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204
    with factory() as session:
        assert session.get(SiteUser, visitor_id) is None
        assert session.query(SiteUserOAuthAccount).filter_by(site_user_id=visitor_id).count() == 0
        assert session.query(SiteUserSession).filter_by(site_user_id=visitor_id).count() == 0
    assert get_waline_record_by_id(record_id=comment.id) is None
    assert get_waline_record_by_id(record_id=comment_reply.id) is None
    assert get_waline_record_by_id(record_id=guestbook.id) is None


def test_visitor_waline_deletion_uses_one_recursive_tree_query() -> None:
    from aerisun.core.settings import get_settings
    from aerisun.domain.waline.service import (
        _delete_waline_records_for_site_user,
        connect_waline_db,
        create_waline_record,
        get_waline_record_by_id,
    )

    visitor_id = "recursive-delete-visitor"
    root = create_waline_record(
        comment="visitor root",
        nick="Visitor",
        mail="visitor@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        site_user_id=visitor_id,
        avatar_key=f"site-user-{visitor_id}",
    )
    child = create_waline_record(
        comment="other visitor reply",
        nick="Other visitor",
        mail="other@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        parent_id=root.id,
        site_user_id="other-visitor",
    )
    grandchild = create_waline_record(
        comment="nested reply",
        nick="Third visitor",
        mail="third@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        parent_id=child.id,
        site_user_id="third-visitor",
    )
    unrelated = create_waline_record(
        comment="unrelated root",
        nick="Unrelated visitor",
        mail="unrelated@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        site_user_id="unrelated-visitor",
    )

    statements: list[str] = []
    with connect_waline_db(get_settings().waline_db_path) as connection:
        connection.set_trace_callback(statements.append)
        deleted = _delete_waline_records_for_site_user(connection, site_user_id=visitor_id)
        connection.set_trace_callback(None)

    assert deleted == 3
    assert any("WITH RECURSIVE" in statement.upper() for statement in statements)
    assert not any("SELECT id FROM wl_comment WHERE pid" in statement for statement in statements)
    assert get_waline_record_by_id(record_id=root.id) is None
    assert get_waline_record_by_id(record_id=child.id) is None
    assert get_waline_record_by_id(record_id=grandchild.id) is None
    assert get_waline_record_by_id(record_id=unrelated.id) is not None


def test_admin_cannot_delete_unknown_visitor(client, admin_headers) -> None:
    response = client.delete(
        "/api/v1/admin/visitors/users/missing-visitor",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_admin_cannot_delete_visitor_bound_to_an_admin_identity(client, admin_headers) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.models import SiteAdminIdentity, SiteUser

    factory = get_session_factory()
    with factory() as session:
        visitor = _create_visitor_with_oauth_and_session(session)
        visitor_id = visitor.id
        admin = session.query(AdminUser).filter_by(username="test-admin").one()
        session.add(
            SiteAdminIdentity(
                site_user_id=visitor_id,
                admin_user_id=admin.id,
                provider="google",
                identifier="visitor-delete-admin-binding",
                email=visitor.email,
                provider_display_name=visitor.display_name,
            )
        )
        session.commit()

    response = client.delete(
        f"/api/v1/admin/visitors/users/{visitor_id}",
        headers=admin_headers,
    )

    assert response.status_code == 409
    with factory() as session:
        assert session.get(SiteUser, visitor_id) is not None


def test_delete_visitor_rolls_back_waline_records_when_main_database_commit_fails(
    seeded_session,
    monkeypatch,
) -> None:
    from aerisun.domain.site_auth.service import delete_site_user_admin
    from aerisun.domain.waline.service import create_waline_record, get_waline_record_by_id

    visitor = _create_visitor_with_oauth_and_session(seeded_session)
    comment = create_waline_record(
        comment="must remain when account deletion fails",
        nick="Visitor to delete",
        mail="visitor-delete@example.com",
        link=None,
        status="approved",
        url="/posts/test-post",
        site_user_id=visitor.id,
    )

    def fail_commit() -> None:
        raise RuntimeError("main database commit failed")

    monkeypatch.setattr(seeded_session, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="main database commit failed"):
        delete_site_user_admin(seeded_session, visitor.id)

    assert get_waline_record_by_id(record_id=comment.id) is not None


def test_delete_visitor_openapi_contract_declares_missing_and_admin_binding_errors(client) -> None:
    responses = client.get("/openapi.json").json()["paths"]["/api/v1/admin/visitors/users/{user_id}"]["delete"][
        "responses"
    ]

    assert "404" in responses
    assert "409" in responses

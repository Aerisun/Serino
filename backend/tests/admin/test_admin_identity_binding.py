from __future__ import annotations


def _create_google_site_user(session, *, email: str, provider_subject: str):
    from aerisun.core.time import shanghai_now
    from aerisun.domain.site_auth.models import SiteUser, SiteUserOAuthAccount

    user = SiteUser(
        email=email,
        display_name="Google Admin",
        avatar_url="https://example.com/google-admin.png",
        primary_auth_provider="google",
        last_login_at=shanghai_now(),
    )
    session.add(user)
    session.flush()
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
    return user


def test_upsert_admin_identity_is_idempotent_for_existing_provider_identifier(
    seeded_session,
    admin_user,
) -> None:
    from aerisun.domain.site_auth.admin_binding import upsert_admin_identity
    from aerisun.domain.site_auth.models import SiteAdminIdentity

    user = _create_google_site_user(
        seeded_session,
        email="google-admin@example.com",
        provider_subject="google-sub-123",
    )

    first = upsert_admin_identity(
        seeded_session,
        site_user=user,
        admin_user_id=admin_user.id,
        provider="google",
        identifier="google-sub-123",
        email="google-admin@example.com",
        provider_display_name="Google Admin",
    )
    second = upsert_admin_identity(
        seeded_session,
        site_user=user,
        admin_user_id=admin_user.id,
        provider="google",
        identifier="google-sub-123",
        email="google-admin@example.com",
        provider_display_name="Google Admin",
    )

    identities = (
        seeded_session.query(SiteAdminIdentity)
        .filter(
            SiteAdminIdentity.provider == "google",
            SiteAdminIdentity.identifier == "google-sub-123",
        )
        .all()
    )
    assert second.id == first.id
    assert len(identities) == 1


def test_upsert_admin_identity_recovers_from_duplicate_insert_race(
    seeded_session,
    admin_user,
    monkeypatch,
) -> None:
    from aerisun.domain.site_auth import repository as repo
    from aerisun.domain.site_auth.admin_binding import upsert_admin_identity
    from aerisun.domain.site_auth.models import SiteAdminIdentity

    user = _create_google_site_user(
        seeded_session,
        email="raced-google-admin@example.com",
        provider_subject="raced-google-sub-123",
    )
    existing = upsert_admin_identity(
        seeded_session,
        site_user=user,
        admin_user_id=admin_user.id,
        provider="google",
        identifier="raced-google-sub-123",
        email="raced-google-admin@example.com",
        provider_display_name="Google Admin",
    )

    original_find_provider_identifier = repo.find_admin_identity_by_provider_identifier
    original_find_user_provider = repo.find_admin_identity_for_user_provider
    provider_identifier_misses = 1
    user_provider_misses = 1

    def miss_provider_identifier_once(session, *, provider: str, identifier: str):
        nonlocal provider_identifier_misses
        if provider_identifier_misses:
            provider_identifier_misses -= 1
            return None
        return original_find_provider_identifier(
            session,
            provider=provider,
            identifier=identifier,
        )

    def miss_user_provider_once(session, *, site_user_id: str, provider: str):
        nonlocal user_provider_misses
        if user_provider_misses:
            user_provider_misses -= 1
            return None
        return original_find_user_provider(
            session,
            site_user_id=site_user_id,
            provider=provider,
        )

    monkeypatch.setattr(
        repo,
        "find_admin_identity_by_provider_identifier",
        miss_provider_identifier_once,
    )
    monkeypatch.setattr(
        repo,
        "find_admin_identity_for_user_provider",
        miss_user_provider_once,
    )

    recovered = upsert_admin_identity(
        seeded_session,
        site_user=user,
        admin_user_id=admin_user.id,
        provider="google",
        identifier="raced-google-sub-123",
        email="raced-google-admin@example.com",
        provider_display_name="Google Admin",
    )

    identities = (
        seeded_session.query(SiteAdminIdentity)
        .filter(
            SiteAdminIdentity.provider == "google",
            SiteAdminIdentity.identifier == "raced-google-sub-123",
        )
        .all()
    )
    assert recovered.id == existing.id
    assert len(identities) == 1

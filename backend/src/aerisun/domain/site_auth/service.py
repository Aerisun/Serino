from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.schemas import SiteUserAdminRead, SiteUserOAuthAccountAdminRead

from .admin_binding import (  # noqa: F401
    bind_site_admin_identity_by_email,
    bind_site_admin_identity_from_current_user,
    delete_site_admin_identity,
    get_admin_login_options,
    list_site_admin_identities_admin,
    resolve_admin_user_id_for_email,
    resolve_admin_user_id_for_site_user,
)
from .config_service import (  # noqa: F401
    build_default_site_auth_config,
    get_site_auth_admin_config,
    update_site_auth_admin_config,
)
from .oauth import build_oauth_authorization_url, complete_oauth_login  # noqa: F401
from .profile import (  # noqa: F401
    build_avatar_candidate_batch,
    get_admin_comment_identity,
    get_auth_state,
    is_site_user_admin,
    login_with_email,
    update_site_user_profile,
)
from .sessions import destroy_site_session, validate_site_session_token  # noqa: F401
from .shared import ALLOWED_OAUTH_PROVIDERS


def list_site_users_admin(
    session: Session,
    *,
    auth_mode: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SiteUserAdminRead], int]:
    users, total = repo.list_site_users(
        session,
        auth_mode=auth_mode,
        search=search,
        page=page,
        page_size=page_size,
    )
    account_map = repo.list_oauth_accounts_by_user_ids(session, [user.id for user in users])
    items = [
        SiteUserAdminRead(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            primary_auth_provider=user.primary_auth_provider,
            auth_mode="binding" if account_map.get(user.id) else "email",
            oauth_accounts=[
                SiteUserOAuthAccountAdminRead(
                    provider=account.provider,
                    provider_email=account.provider_email,
                    provider_display_name=account.provider_display_name,
                    created_at=account.created_at,
                )
                for account in account_map.get(user.id, [])
                if account.provider in ALLOWED_OAUTH_PROVIDERS
            ],
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )
        for user in users
    ]
    return items, total

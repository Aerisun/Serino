from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class SiteAuthAvatarCandidate(ModelBase):
    key: str = Field(description="Avatar option key")
    label: str = Field(description="Avatar option label")
    avatar_url: str = Field(description="Avatar option URL")


class SiteAuthUserRead(ModelBase):
    id: str = Field(description="Public site user id")
    email: str = Field(description="Login identifier email")
    display_name: str = Field(description="Display name")
    avatar_url: str = Field(description="Public avatar URL")
    effective_display_name: str = Field(description="Display name currently used in public surfaces")
    effective_avatar_url: str = Field(description="Avatar currently used in public surfaces")
    primary_auth_provider: str = Field(description="Primary auth provider")
    is_admin: bool = Field(default=False, description="Whether the current site session is admin-elevated")
    can_access_admin_console: bool = Field(
        default=False,
        description="Whether the current admin-elevated site session can enter the admin console",
    )
    last_login_at: datetime | None = Field(default=None, description="Last login time")


class SiteAuthStateRead(BaseModel):
    authenticated: bool = Field(description="Whether the current request is authenticated")
    user: SiteAuthUserRead | None = Field(default=None, description="Current site user")
    email_login_enabled: bool = Field(default=True, description="Whether email login is enabled")
    oauth_providers: list[str] = Field(default_factory=list, description="Enabled oauth providers")


class EmailLoginRequest(BaseModel):
    email: str = Field(description="Email identifier")
    display_name: str | None = Field(default=None, description="Optional display name for first login")
    avatar_url: str | None = Field(default=None, description="Optional avatar URL for first login")
    admin_password: str | None = Field(default=None, description="Shared admin email password when elevation is needed")


class EmailLoginResponse(BaseModel):
    authenticated: bool = Field(description="Whether a login session was created")
    requires_profile: bool = Field(default=False, description="Whether first-login profile setup is required")
    requires_admin_password: bool = Field(
        default=False,
        description="Whether admin email login requires the shared admin password before creating a session",
    )
    user: SiteAuthUserRead | None = Field(default=None, description="Current site user when authenticated")
    suggested_display_name: str | None = Field(default=None, description="Suggested display name for first login")
    avatar_candidates: list[SiteAuthAvatarCandidate] = Field(default_factory=list, description="Avatar candidates")
    avatar_batch: int = Field(default=0, description="Current avatar candidate batch")
    avatar_total_batches: int = Field(default=1, description="Total number of avatar candidate batches")


class SiteAuthAvatarCandidateBatchRead(BaseModel):
    batch: int = Field(description="Current avatar candidate batch")
    total_batches: int = Field(description="Total number of avatar candidate batches")
    avatar_candidates: list[SiteAuthAvatarCandidate] = Field(default_factory=list, description="Avatar candidates")


class SiteAuthProfileUpdateRequest(BaseModel):
    display_name: str = Field(description="Updated display name")
    avatar_url: str = Field(description="Updated avatar URL")


class SiteAuthConfigAdminRead(ModelBase):
    id: str = Field(description="Visitor auth config id")
    email_login_enabled: bool = Field(description="Whether email login is enabled")
    visitor_oauth_providers: list[str] = Field(
        default_factory=list,
        description="OAuth providers enabled for visitor binding",
    )
    admin_auth_methods: list[str] = Field(
        default_factory=list,
        description="Auth methods reserved for admin-side usage",
    )
    admin_console_auth_methods: list[str] = Field(
        default_factory=list,
        description="Admin-elevated auth methods that are allowed to enter the admin console",
    )
    admin_email_enabled: bool = Field(description="Whether email can be used as an admin identity")
    admin_email_password_set: bool = Field(description="Whether the shared admin email password has been configured")
    google_client_id: str = Field(description="Google OAuth client id")
    google_client_secret: str = Field(description="Google OAuth client secret")
    github_client_id: str = Field(description="GitHub OAuth client id")
    github_client_secret: str = Field(description="GitHub OAuth client secret")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")


class SiteAuthConfigAdminUpdate(BaseModel):
    email_login_enabled: bool | None = Field(default=None, description="Whether email login remains enabled")
    visitor_oauth_providers: list[str] | None = Field(
        default=None,
        description="OAuth providers enabled for visitor binding",
    )
    admin_auth_methods: list[str] | None = Field(
        default=None,
        description="Auth methods reserved for admin-side usage",
    )
    admin_console_auth_methods: list[str] | None = Field(
        default=None,
        description="Admin-elevated auth methods that are allowed to enter the admin console",
    )
    admin_email_enabled: bool | None = Field(default=None, description="Whether email can be used as admin login")
    admin_email_password: str | None = Field(
        default=None,
        description="Shared admin email password used by all bound admin email identities",
    )
    google_client_id: str | None = Field(default=None, description="Google OAuth client id")
    google_client_secret: str | None = Field(default=None, description="Google OAuth client secret")
    github_client_id: str | None = Field(default=None, description="GitHub OAuth client id")
    github_client_secret: str | None = Field(default=None, description="GitHub OAuth client secret")


class SiteUserOAuthAccountAdminRead(ModelBase):
    provider: Literal["google", "github"] = Field(description="OAuth provider")
    provider_email: str | None = Field(default=None, description="Provider-side email")
    provider_display_name: str | None = Field(default=None, description="Provider-side display name")
    created_at: datetime = Field(description="Binding creation time")


class SiteUserAdminRead(ModelBase):
    id: str = Field(description="Site user id")
    email: str = Field(description="Login email identifier")
    display_name: str = Field(description="Current display name")
    avatar_url: str = Field(description="Current avatar URL")
    primary_auth_provider: str = Field(description="Primary auth provider")
    auth_mode: Literal["email", "binding"] = Field(
        description="Whether this user is email-only or has OAuth bindings",
    )
    oauth_accounts: list[SiteUserOAuthAccountAdminRead] = Field(
        default_factory=list,
        description="Linked OAuth accounts",
    )
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")
    last_login_at: datetime | None = Field(default=None, description="Last login time")


class SiteAdminIdentityAdminRead(ModelBase):
    id: str = Field(description="Admin identity id")
    site_user_id: str = Field(description="Bound site user id")
    provider: Literal["email", "google", "github"] = Field(description="Bound auth provider")
    identifier: str = Field(description="Provider identifier used for the binding")
    email: str = Field(description="Normalized email used by the binding")
    site_user_display_name: str = Field(description="Underlying site user display name")
    site_user_avatar_url: str = Field(description="Underlying site user avatar")
    provider_display_name: str | None = Field(default=None, description="Provider-side display name if present")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")


class SiteAdminEmailIdentityBindRequest(BaseModel):
    email: str = Field(description="Admin email identifier")


class OAuthStartResponse(BaseModel):
    authorization_url: str = Field(description="Provider authorization URL")


class OAuthProviderCallbackResult(BaseModel):
    provider: Literal["google", "github"] = Field(description="OAuth provider")
    email: str = Field(description="Provider email")
    display_name: str = Field(description="Provider display name")
    avatar_url: str = Field(description="Provider avatar URL")
    provider_subject: str = Field(description="Provider subject id")

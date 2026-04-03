from __future__ import annotations

import base64
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import AuthenticationFailed, ValidationError
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.schemas import OAuthProviderCallbackResult

from .config_service import enabled_oauth_providers, oauth_credentials
from .profile import build_avatar_candidates, suggest_display_name
from .sessions import create_site_session
from .shared import ALLOWED_OAUTH_PROVIDERS, normalize_display_name, normalize_email, normalize_return_to

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OAuthStatePayload:
    provider: str
    state: str
    return_to: str


def build_oauth_state_cookie(provider: str, state: str, return_to: str) -> str:
    payload = {"provider": provider, "state": state, "return_to": normalize_return_to(return_to)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def parse_oauth_state_cookie(raw: str | None) -> OAuthStatePayload | None:
    if not raw:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
    except Exception:
        logger.warning("Failed to parse OAuth state cookie", exc_info=True)
        return None
    provider = str(payload.get("provider") or "").strip().lower()
    state = str(payload.get("state") or "").strip()
    return_to = normalize_return_to(str(payload.get("return_to") or "/"))
    if provider not in ALLOWED_OAUTH_PROVIDERS or not state:
        return None
    return OAuthStatePayload(provider=provider, state=state, return_to=return_to)


def build_oauth_authorization_url(
    session: Session,
    provider: str,
    return_to: str,
    *,
    callback_url: str,
) -> tuple[str, str]:
    normalized = provider.strip().lower()
    state = secrets.token_urlsafe(24)

    if normalized not in enabled_oauth_providers(session):
        raise ValidationError("当前站点未启用该登录方式。")

    if normalized == "github":
        client_id, _ = oauth_credentials(session, "github")
        if not client_id:
            raise ValidationError("GitHub 登录尚未配置。")
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
                "state": state,
            }
        )
        auth_url = f"https://github.com/login/oauth/authorize?{params}"
        return auth_url, build_oauth_state_cookie("github", state, return_to)

    if normalized == "google":
        client_id, _ = oauth_credentials(session, "google")
        if not client_id:
            raise ValidationError("Google 登录尚未配置。")
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "online",
                "prompt": "select_account",
                "state": state,
            }
        )
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
        return auth_url, build_oauth_state_cookie("google", state, return_to)

    raise ValidationError("不支持的登录方式。")


def exchange_github_code(session: Session, code: str, *, callback_url: str) -> OAuthProviderCallbackResult:
    client_id, client_secret = oauth_credentials(session, "github")
    token_response = httpx.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": callback_url,
        },
        timeout=8.0,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("GitHub 登录失败。")

    user_response = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        timeout=8.0,
    )
    user_response.raise_for_status()
    user_payload = user_response.json()

    email_response = httpx.get(
        "https://api.github.com/user/emails",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        timeout=8.0,
    )
    email_response.raise_for_status()
    email_payload = email_response.json()
    primary_email = ""
    if isinstance(email_payload, list):
        primary = next((item for item in email_payload if item.get("primary")), None)
        if primary is None and email_payload:
            primary = email_payload[0]
        if primary:
            primary_email = str(primary.get("email") or "")

    return OAuthProviderCallbackResult(
        provider="github",
        email=normalize_email(primary_email),
        display_name=normalize_display_name(
            str(user_payload.get("name") or user_payload.get("login") or "GitHub User")
        ),
        avatar_url=str(user_payload.get("avatar_url") or ""),
        provider_subject=str(user_payload.get("id") or ""),
    )


def exchange_google_code(session: Session, code: str, *, callback_url: str) -> OAuthProviderCallbackResult:
    client_id, client_secret = oauth_credentials(session, "google")
    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": callback_url,
        },
        timeout=8.0,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("Google 登录失败。")

    user_response = httpx.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=8.0,
    )
    user_response.raise_for_status()
    user_payload = user_response.json()

    return OAuthProviderCallbackResult(
        provider="google",
        email=normalize_email(str(user_payload.get("email") or "")),
        display_name=normalize_display_name(str(user_payload.get("name") or "Google User")),
        avatar_url=str(user_payload.get("picture") or ""),
        provider_subject=str(user_payload.get("sub") or ""),
    )


def complete_oauth_login(
    session: Session,
    provider: str,
    code: str,
    state: str,
    state_cookie: str | None,
    *,
    callback_url: str,
) -> tuple[str, str]:
    payload = parse_oauth_state_cookie(state_cookie)
    if payload is None or payload.provider != provider or payload.state != state:
        raise AuthenticationFailed("登录状态已失效，请重新开始。")

    if provider == "github":
        profile = exchange_github_code(session, code, callback_url=callback_url)
    elif provider == "google":
        profile = exchange_google_code(session, code, callback_url=callback_url)
    else:
        raise ValidationError("不支持的登录方式。")

    if not profile.email:
        raise ValidationError("当前登录方式没有返回可用邮箱，无法建立站点身份。")

    oauth_account = repo.find_oauth_account(session, provider=provider, provider_subject=profile.provider_subject)
    user = repo.find_user_by_email(session, profile.email)

    if oauth_account is not None:
        user = repo.find_user_by_id(session, oauth_account.site_user_id)

    if user is None:
        user = repo.create_user(
            session,
            email=profile.email,
            display_name=profile.display_name or suggest_display_name(profile.email),
            avatar_url=profile.avatar_url or build_avatar_candidates(profile.email, 1)[0].avatar_url,
            primary_auth_provider=provider,
            last_login_at=datetime.now(UTC),
        )
        session.flush()
    else:
        user.display_name = profile.display_name or user.display_name
        if profile.avatar_url:
            user.avatar_url = profile.avatar_url
        user.primary_auth_provider = provider
        user.last_login_at = datetime.now(UTC)

    if oauth_account is None:
        repo.create_oauth_account(
            session,
            site_user_id=user.id,
            provider=provider,
            provider_subject=profile.provider_subject,
            provider_email=profile.email,
            provider_display_name=profile.display_name,
            provider_avatar_url=profile.avatar_url,
        )
    else:
        oauth_account.provider_email = profile.email
        oauth_account.provider_display_name = profile.display_name
        oauth_account.provider_avatar_url = profile.avatar_url

    session.commit()
    session.refresh(user)
    admin_verified_provider = None
    if provider in enabled_oauth_providers(session):
        identity = repo.find_admin_identity_by_provider_identifier(
            session,
            provider=provider,
            identifier=profile.provider_subject,
        )
        if identity is not None and identity.site_user_id == user.id and identity.admin_user_id:
            admin_verified_provider = provider
    token = create_site_session(session, user.id, admin_verified_provider=admin_verified_provider)
    return token, payload.return_to

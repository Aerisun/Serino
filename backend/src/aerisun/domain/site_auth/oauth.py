from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from aerisun.core.time import shanghai_now
from aerisun.domain.exceptions import AuthenticationFailed, ValidationError
from aerisun.domain.outbound_proxy.service import require_outbound_proxy_scope, send_outbound_request
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.schemas import OAuthProviderCallbackResult

from .config_service import enabled_oauth_providers, oauth_credentials
from .profile import build_avatar_candidates, suggest_display_name
from .sessions import create_site_session
from .shared import ALLOWED_OAUTH_PROVIDERS, normalize_display_name, normalize_email, normalize_return_to

logger = logging.getLogger(__name__)
OAUTH_STATE_TTL_SECONDS = 600
_OAUTH_STATE_SECRET_FILE_NAME = "oauth-state-secret"


@dataclass(slots=True)
class OAuthStatePayload:
    provider: str
    state: str
    return_to: str


def build_oauth_state_cookie(provider: str, state: str, return_to: str) -> str:
    payload = {
        "provider": provider,
        "state": state,
        "return_to": normalize_return_to(return_to),
        "iat": int(time.time()),
    }
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(
        _oauth_state_secret(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"v1.{encoded_payload}.{_base64url_encode(signature)}"


def parse_oauth_state_cookie(raw: str | None) -> OAuthStatePayload | None:
    if not raw:
        return None
    try:
        payload = _decode_oauth_state_cookie(raw)
    except Exception:
        logger.warning("Failed to parse OAuth state cookie", exc_info=True)
        return None
    provider = str(payload.get("provider") or "").strip().lower()
    state = str(payload.get("state") or "").strip()
    return_to = normalize_return_to(str(payload.get("return_to") or "/"))
    if provider not in ALLOWED_OAUTH_PROVIDERS or not state:
        return None
    return OAuthStatePayload(provider=provider, state=state, return_to=return_to)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _oauth_state_secret() -> bytes:
    from aerisun.core.settings import get_settings

    settings = get_settings()
    configured = str(getattr(settings, "oauth_state_secret", "") or "").strip()
    if configured:
        return configured.encode("utf-8")

    secret_path = settings.secrets_dir / _OAUTH_STATE_SECRET_FILE_NAME
    try:
        existing = secret_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""
    if existing:
        return existing.encode("utf-8")

    secret_path.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(48)
    try:
        fd = secret_path.open("x", encoding="utf-8")
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip().encode("utf-8")
    with fd:
        fd.write(generated)
    secret_path.chmod(0o600)
    return generated.encode("utf-8")


def _decode_oauth_state_cookie(raw: str) -> dict[str, object]:
    version, encoded_payload, encoded_signature = raw.split(".", 2)
    if version != "v1" or not encoded_payload or not encoded_signature:
        raise ValueError("Unsupported OAuth state cookie")
    expected_signature = hmac.new(
        _oauth_state_secret(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    provided_signature = _base64url_decode(encoded_signature)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid OAuth state signature")
    payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid OAuth state payload")
    issued_at = int(payload.get("iat") or 0)
    if issued_at <= 0 or int(time.time()) - issued_at > OAUTH_STATE_TTL_SECONDS:
        raise ValueError("Expired OAuth state cookie")
    return payload


def _provider_label(provider: str) -> str:
    return "GitHub" if provider == "github" else "Google"


def _safe_json_object(response: httpx.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_provider_error(payload: dict[str, object]) -> str:
    for key in ("error_description", "error", "message"):
        value = str(payload.get(key) or "").strip()
        if value:
            return " ".join(value.split())
    return ""


def _oauth_failure(
    provider: str,
    message: str,
    *,
    payload: dict[str, object] | None = None,
    exc: Exception | None = None,
) -> AuthenticationFailed:
    upstream_error = _extract_provider_error(payload or {})
    detail = f"{_provider_label(provider)} 登录失败，{message}"
    if upstream_error:
        detail = f"{detail}（{upstream_error[:160]}）"
    if exc is not None:
        logger.warning("%s OAuth request failed", provider, exc_info=exc)
    elif payload:
        logger.warning("%s OAuth response rejected: %s", provider, payload)
    return AuthenticationFailed(detail)


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
    require_outbound_proxy_scope(session, scope="oauth")

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
    try:
        token_response = send_outbound_request(
            session,
            scope="oauth",
            method="POST",
            url="https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": callback_url,
            },
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        raise _oauth_failure("github", "暂时无法连接 GitHub 认证服务，请稍后再试。", exc=exc) from exc
    token_payload = _safe_json_object(token_response)
    if token_response.is_error:
        raise _oauth_failure(
            "github",
            "请检查回调地址、Client ID 和 Client Secret 是否与 GitHub OAuth App 配置一致。",
            payload=token_payload,
        )
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise AuthenticationFailed("GitHub 登录失败，GitHub 没有返回可用的 access token。")

    try:
        user_response = send_outbound_request(
            session,
            scope="oauth",
            method="GET",
            url="https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        raise _oauth_failure("github", "读取 GitHub 账号资料失败，请稍后再试。", exc=exc) from exc
    user_payload = _safe_json_object(user_response)
    if user_response.is_error:
        raise _oauth_failure("github", "读取 GitHub 账号资料失败，请稍后再试。", payload=user_payload)

    try:
        email_response = send_outbound_request(
            session,
            scope="oauth",
            method="GET",
            url="https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        raise _oauth_failure("github", "读取 GitHub 账号邮箱失败，请稍后再试。", exc=exc) from exc
    if email_response.is_error:
        raise _oauth_failure("github", "读取 GitHub 账号邮箱失败，请稍后再试。")
    try:
        email_payload = email_response.json()
    except ValueError:
        email_payload = []
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
    try:
        token_response = send_outbound_request(
            session,
            scope="oauth",
            method="POST",
            url="https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_url,
            },
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        raise _oauth_failure("google", "暂时无法连接 Google 认证服务，请稍后再试。", exc=exc) from exc
    token_payload = _safe_json_object(token_response)
    if token_response.is_error:
        raise _oauth_failure(
            "google",
            "请检查回调地址、Client ID 和 Client Secret 是否与 Google Cloud Console 配置一致。",
            payload=token_payload,
        )
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise AuthenticationFailed("Google 登录失败，Google 没有返回可用的 access token。")

    try:
        user_response = send_outbound_request(
            session,
            scope="oauth",
            method="GET",
            url="https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        raise _oauth_failure("google", "读取 Google 账号资料失败，请稍后再试。", exc=exc) from exc
    user_payload = _safe_json_object(user_response)
    if user_response.is_error:
        raise _oauth_failure("google", "读取 Google 账号资料失败，请稍后再试。", payload=user_payload)

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
            last_login_at=shanghai_now(),
        )
        session.flush()
    else:
        user.display_name = profile.display_name or user.display_name
        if profile.avatar_url:
            user.avatar_url = profile.avatar_url
        user.primary_auth_provider = provider
        user.last_login_at = shanghai_now()

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

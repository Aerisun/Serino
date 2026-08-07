from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from aerisun.core.time import normalize_shanghai_datetime, shanghai_now
from aerisun.domain.exceptions import DomainError
from aerisun.domain.iam import repository as iam_repo
from aerisun.domain.iam.models import AdminSession
from aerisun.domain.iam.service import validate_admin_session
from aerisun.domain.media.models import Asset

ASSET_PREVIEW_TOKEN_TTL_SECONDS = 10 * 60
_MAX_TOKEN_LENGTH = 4096


@dataclass(frozen=True, slots=True)
class AssetPreviewGrant:
    token: str
    expires_at: datetime


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def create_asset_preview_grant(
    *,
    asset: Asset,
    admin_session: AdminSession,
) -> AssetPreviewGrant:
    now = shanghai_now()
    session_expires_at = normalize_shanghai_datetime(admin_session.expires_at)
    expires_at = min(
        now + timedelta(seconds=ASSET_PREVIEW_TOKEN_TTL_SECONDS),
        session_expires_at,
    )
    payload = {
        "asset_id": asset.id,
        "exp": int(expires_at.timestamp()),
        "resource_key": asset.resource_key,
        "session_id": admin_session.id,
    }
    encoded_payload = _base64url_encode(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        admin_session.session_token.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return AssetPreviewGrant(
        token=f"v1.{encoded_payload}.{_base64url_encode(signature)}",
        expires_at=expires_at,
    )


def validate_asset_preview_grant(
    session: Session,
    *,
    asset: Asset,
    token: str | None,
) -> bool:
    raw = str(token or "").strip()
    if not raw or len(raw) > _MAX_TOKEN_LENGTH:
        return False
    try:
        version, encoded_payload, encoded_signature = raw.split(".", 2)
        if version != "v1" or not encoded_payload or not encoded_signature:
            return False
        payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
        if not isinstance(payload, dict):
            return False
        session_id = str(payload.get("session_id") or "")
        expires_at = int(payload.get("exp") or 0)
        if (
            not session_id
            or expires_at < int(time.time())
            or str(payload.get("asset_id") or "") != asset.id
            or str(payload.get("resource_key") or "") != asset.resource_key
        ):
            return False
        admin_session = iam_repo.find_session_by_id(session, session_id)
        if admin_session is None:
            return False
        expected_signature = hmac.new(
            admin_session.session_token.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return False
        validate_admin_session(session, admin_session)
        return True
    except (DomainError, UnicodeDecodeError, ValueError, TypeError, OverflowError, binascii.Error):
        return False

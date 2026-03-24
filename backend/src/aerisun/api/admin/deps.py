from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser, ApiKey
from aerisun.domain.iam.service import validate_api_key, validate_session_token

_bearer = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AdminUser:
    try:
        return validate_session_token(session, credentials.credentials)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_api_key_scopes(*required_scopes: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        session: Session = Depends(get_session),
    ) -> ApiKey:
        try:
            return validate_api_key(session, credentials.credentials, required_scopes)
        except PermissionError as exc:
            detail = str(exc)
            code = status.HTTP_403_FORBIDDEN if "scope" in detail.lower() else status.HTTP_401_UNAUTHORIZED
            raise HTTPException(status_code=code, detail=detail) from exc

    return dependency

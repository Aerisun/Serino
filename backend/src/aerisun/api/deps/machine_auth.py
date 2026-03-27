from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import ApiKey
from aerisun.domain.iam.service import validate_api_key

_bearer = HTTPBearer()


def require_api_key_scopes(*required_scopes: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        session: Session = Depends(get_session),
    ) -> ApiKey:
        return validate_api_key(session, credentials.credentials, required_scopes)

    return dependency

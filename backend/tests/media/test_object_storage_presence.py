from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from aerisun.domain.media.object_storage import BitifulObjectStorageProvider


class _HeadErrorClient:
    def __init__(self, *, code: str, status: int) -> None:
        self.code = code
        self.status = status

    def head_object(self, **_kwargs):
        raise ClientError(
            {
                "Error": {"Code": self.code, "Message": self.code},
                "ResponseMetadata": {"HTTPStatusCode": self.status},
            },
            "HeadObject",
        )


def _provider_with_head_error(*, code: str, status: int) -> BitifulObjectStorageProvider:
    provider = object.__new__(BitifulObjectStorageProvider)
    provider._bucket = "test-bucket"
    provider._client = _HeadErrorClient(code=code, status=status)
    return provider


def test_find_object_returns_none_only_for_authoritative_not_found() -> None:
    provider = _provider_with_head_error(code="NoSuchKey", status=404)

    assert provider.find_object(object_key="missing") is None


def test_find_object_does_not_turn_access_denied_into_missing() -> None:
    provider = _provider_with_head_error(code="AccessDenied", status=403)

    with pytest.raises(ClientError):
        provider.find_object(object_key="protected")

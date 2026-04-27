from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from aerisun.core.schemas import ModelBase


def _normalize_proxy_port(value: Any) -> Any:
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.isdigit():
            return int(candidate)
        url_candidate = candidate if "://" in candidate else f"http://{candidate}"
        try:
            port = urlsplit(url_candidate).port
        except ValueError:
            port = None
        if port is not None:
            return port
    return value


class OutboundProxyConfigRead(ModelBase):
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    webhook_enabled: bool = False
    oauth_enabled: bool = False

    @field_validator("proxy_port", mode="before")
    @classmethod
    def normalize_proxy_port(cls, value: Any) -> Any:
        return _normalize_proxy_port(value)


class OutboundProxyConfigUpdate(BaseModel):
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    webhook_enabled: bool | None = None
    oauth_enabled: bool | None = None

    @field_validator("proxy_port", mode="before")
    @classmethod
    def normalize_proxy_port(cls, value: Any) -> Any:
        return _normalize_proxy_port(value)


class OutboundProxyHealthRead(ModelBase):
    ok: bool
    proxy_url: str
    summary: str
    latency_ms: int | None = None
    status_code: int | None = None

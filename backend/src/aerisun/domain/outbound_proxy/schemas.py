from __future__ import annotations

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class OutboundProxyConfigRead(ModelBase):
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    webhook_enabled: bool = False
    oauth_enabled: bool = False


class OutboundProxyConfigUpdate(BaseModel):
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    webhook_enabled: bool | None = None
    oauth_enabled: bool | None = None


class OutboundProxyHealthRead(ModelBase):
    ok: bool
    proxy_url: str
    summary: str
    latency_ms: int | None = None
    status_code: int | None = None

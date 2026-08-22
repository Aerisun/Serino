from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ServiceForwardSource = Literal["local", "tailscale"]
ServiceForwardStatus = Literal["unchecked", "reachable", "unreachable"]
_SLUG_LABEL_PATTERN = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_SLUG_SEGMENT_PATTERN = rf"{_SLUG_LABEL_PATTERN}(?:\.{_SLUG_LABEL_PATTERN})*"


class ServiceForwardWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    slug: str = Field(
        max_length=255,
        pattern=rf"^{_SLUG_SEGMENT_PATTERN}(?:/{_SLUG_SEGMENT_PATTERN})*$",
    )
    source: ServiceForwardSource
    port: int | None = Field(default=None, ge=1, le=65535)
    target_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("名称不能包含控制字符")
        return value

    @model_validator(mode="after")
    def validate_source_fields(self) -> ServiceForwardWrite:
        if self.source == "local":
            if self.port is None:
                raise ValueError("当前机器来源需要填写端口")
            if self.target_url is not None:
                raise ValueError("当前机器来源只需填写端口")
        else:
            if not self.target_url:
                raise ValueError("Tailscale 来源需要填写服务网址")
            if self.port is not None:
                raise ValueError("Tailscale 来源只需填写服务网址")
        return self


class ServiceForwardRead(BaseModel):
    id: str
    name: str
    slug: str
    path: str
    source: Literal["local", "tailscale", "custom"]
    target_url: str
    public_url: str
    status: ServiceForwardStatus = "unchecked"
    checked_at: datetime | None = None
    status_message: str | None = None

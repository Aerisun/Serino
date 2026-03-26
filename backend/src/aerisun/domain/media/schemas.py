from __future__ import annotations

from datetime import datetime
from typing import Literal

from aerisun.core.schemas import ModelBase


class AssetAdminRead(ModelBase):
    id: str
    file_name: str
    resource_key: str
    visibility: Literal["internal", "public"]
    scope: Literal["system", "user"]
    category: str
    note: str | None
    storage_path: str
    internal_url: str
    public_url: str | None
    mime_type: str | None
    byte_size: int | None
    sha256: str | None
    created_at: datetime
    updated_at: datetime


class AssetAdminUpdate(ModelBase):
    visibility: Literal["internal", "public"] | None = None
    scope: Literal["system", "user"] | None = None
    category: str | None = None
    note: str | None = None

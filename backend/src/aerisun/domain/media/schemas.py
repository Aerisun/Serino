from __future__ import annotations

from datetime import datetime

from aerisun.core.schemas import ModelBase


class AssetAdminRead(ModelBase):
    id: str
    file_name: str
    storage_path: str
    mime_type: str | None
    byte_size: int | None
    sha256: str | None
    created_at: datetime
    updated_at: datetime

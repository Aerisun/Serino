from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthRead(ModelBase):
    status: str
    database_path: str
    timestamp: datetime

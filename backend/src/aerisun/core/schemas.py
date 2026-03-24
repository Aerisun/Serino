from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthRead(ModelBase):
    status: str = Field(description="Service health status")
    database_path: str = Field(description="SQLite database file path")
    timestamp: datetime = Field(description="Current server timestamp")
